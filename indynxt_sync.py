#!/usr/bin/env python3
"""
Indy NXT -> auto-updating ICS feed.  v2

Sources (indynxt.com, server-rendered HTML; no public API):
- Races: the schedule page's event cards (class-anchored regexes).
- Practice/qualifying: each round's detail page (/Schedule/{year}/{slug})
  carries a weekend schedule-table with <h3>day headers and
  schedule-time / schedule-description entries. Non-race 'INDY NXT - *'
  entries become silent session events. Doubleheader pages repeat the
  weekend schedule, so sessions dedupe globally by (date, time, name).

- All times are US Eastern -> converted via zoneinfo (DST-aware)
- 'TBD' race times become all-day events until the source publishes a time
- Season year comes from the page's own event links (self-rolling)
- Round-page fetch failures are non-fatal (sessions are additive);
  the abort guard protects the race backbone
"""
import html
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

URL = "https://www.indynxt.com/schedule"
ROUND_URL = "https://www.indynxt.com/Schedule/{year}/{slug}"
ET = ZoneInfo("America/New_York")
MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
MIN_EVENTS = 10
RACE_MINUTES = 60
SESSION_MINUTES = 45
PREFIXES = ("indy nxt by firestone at ", "grand prix of ", "grand prix at ")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (indynxt-ics-sync)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def clean_title(t):
    low = t.lower()
    for pre in PREFIXES:
        if low.startswith(pre):
            return t[len(pre):].strip()
    return t


def weekend_name(title):
    return re.sub(r"\s*[-\u2013]?\s*Race\s*\d+\s*$", "", title).strip()


def esc(x):
    return x.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


def parse_sessions(page, year):
    """Walk a round page's schedule-table in document order."""
    out = []
    day = None
    pending_time = None
    tok = re.compile(r'<h3>([A-Za-z]+,\s*[A-Z][a-z]{2}\s*\d{1,2})</h3>'
                     r'|schedule-time">([^<]+)<'
                     r'|schedule-description">([^<]+)<')
    for m in tok.finditer(page):
        if m.group(1):
            dm = re.search(r'([A-Z][a-z]{2})\s*(\d{1,2})', m.group(1))
            day = (MONTHS.get(dm.group(1)), int(dm.group(2))) if dm else None
            pending_time = None
        elif m.group(2):
            pending_time = m.group(2).strip()
        elif m.group(3):
            desc = html.unescape(m.group(3)).strip()
            if not desc.upper().startswith("INDY NXT"):
                pending_time = None
                continue
            name = re.sub(r"^INDY NXT\s*[-\u2013]\s*", "", desc, flags=re.I).strip()
            if re.search(r"\brace\b", name, re.I):
                pending_time = None
                continue
            if not (day and day[0] and pending_time):
                pending_time = None
                continue
            tm = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)\s*ET', pending_time)
            if not tm:
                pending_time = None
                continue
            hh = int(tm.group(1)) % 12 + (12 if tm.group(3) == "PM" else 0)
            start = datetime(year, day[0], day[1], hh, int(tm.group(2)),
                             tzinfo=ET).astimezone(timezone.utc)
            out.append((start, name))
            pending_time = None
    return out


def main(out_path):
    page = fetch(URL)
    season_m = re.search(r"(\d{4}) SEASON", page, re.I)
    season_fallback = int(season_m.group(1)) if season_m else datetime.now(timezone.utc).year

    chunks = page.split('class="event-card event-card')[1:]
    seen = set()
    rows = []
    for c in chunks:
        d = re.search(r'event-card-header-date">([^<]+)<', c)
        t = re.search(r'event-card-header-time">([^<]+)<', c)
        ti = re.search(r'<h3 class="event-card-title">([^<]+)<', c)
        if not (d and t and ti):
            continue
        date_s = d.group(1).strip()
        time_s = t.group(1).strip()
        title_full = html.unescape(ti.group(1)).strip()
        key = (date_s, title_full)
        if key in seen:
            continue
        seen.add(key)
        venue_m = re.search(r'TrackLogos/[^"]*"[^>]*alt="([^"]+)"', c)
        venue = html.unescape(venue_m.group(1)).strip() if venue_m else ""
        link = re.search(r'href="https://www\.indynxt\.com/Schedule/(\d{4})/([^"]+)"', c)
        year = int(link.group(1)) if link else season_fallback
        slug = link.group(2) if link else title_full
        dm = re.match(r'([A-Z][a-z]{2}) (\d{1,2})$', date_s)
        if not dm or dm.group(1) not in MONTHS:
            continue
        month, day = MONTHS[dm.group(1)], int(dm.group(2))
        tm = re.match(r'(\d{1,2}):(\d{2}) (AM|PM) ET$', time_s)
        if tm:
            hh = int(tm.group(1)) % 12 + (12 if tm.group(3) == "PM" else 0)
            start = datetime(year, month, day, hh, int(tm.group(2)), tzinfo=ET).astimezone(timezone.utc)
            allday = False
        else:
            start = None
            allday = True
        rows.append((year, month, day, allday, start, title_full,
                     clean_title(title_full), venue, slug))

    if len(rows) < MIN_EVENTS:
        print(f"ABORT: only {len(rows)} events - refusing to overwrite feed.", file=sys.stderr)
        sys.exit(1)

    # ---- sessions from round pages (additive; failures non-fatal) ----
    sess_seen = set()
    sessions = []
    for year, month, day, allday, start, title_full, title, venue, slug in rows:
        try:
            rp = fetch(ROUND_URL.format(year=year, slug=slug))
        except Exception:
            continue
        wname = weekend_name(title)
        for st, name in parse_sessions(rp, year):
            key = (st.strftime("%Y%m%d%H%M"), name.lower())
            if key in sess_seen:
                continue
            sess_seen.add(key)
            sessions.append((st, name, wname, venue, year))

    rows.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    season = rows[0][0]
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//LGS//IndyNXT Auto-Sync//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:Indy NXT",
             "X-WR-CALDESC:" + esc(f"INDY NXT by Firestone (season {season}) - races, "
                                   "practice and qualifying, auto-synced daily from indynxt.com"),
             "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
             "X-PUBLISHED-TTL:PT12H"]

    for year, month, day, allday, start, title_full, title, venue, slug in rows:
        uid = re.sub(r"[^a-z0-9]+", "-", f"indynxt-{year}-{slug}".lower()).strip("-")
        lines += ["BEGIN:VEVENT", f"UID:{uid}@lgs-indynxt", f"DTSTAMP:{now}"]
        if allday:
            d0 = datetime(year, month, day)
            d1 = d0 + timedelta(days=1)
            lines += [f"DTSTART;VALUE=DATE:{d0.strftime('%Y%m%d')}",
                      f"DTEND;VALUE=DATE:{d1.strftime('%Y%m%d')}",
                      f"SUMMARY:{esc('\U0001F3C1 Indy NXT ' + title + ' (time TBD)')}"]
        else:
            end = start + timedelta(minutes=RACE_MINUTES)
            lines += [f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}Z",
                      f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}Z",
                      f"SUMMARY:{esc('\U0001F3C1 Indy NXT ' + title)}"]
        lines += [f"LOCATION:{esc(venue)}",
                  f"DESCRIPTION:{esc(title_full)} - Indy NXT season {year}. "
                  "Times auto-convert to your timezone. Auto-synced daily.",
                  "END:VEVENT"]

    for st, name, wname, venue, year in sessions:
        nslug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        uid = f"indynxt-{st.strftime('%Y%m%d%H%M')}-{nslug}"
        en = st + timedelta(minutes=SESSION_MINUTES)
        desc = (f"{name} - Indy NXT {wname}, season {year}. Times listed in US Eastern "
                "on indynxt.com, auto-converted to your timezone. Auto-synced daily.")
        lines += ["BEGIN:VEVENT", f"UID:{uid}@lgs-indynxt", f"DTSTAMP:{now}",
                  f"DTSTART:{st.strftime('%Y%m%dT%H%M%S')}Z",
                  f"DTEND:{en.strftime('%Y%m%dT%H%M%S')}Z",
                  "SUMMARY:" + esc(f"Indy NXT {wname} - {name}"),
                  "LOCATION:" + esc(venue),
                  "DESCRIPTION:" + esc(desc),
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")

    with open(out_path, "w", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")
    print(f"OK: wrote {len(rows)} races + {len(sessions)} sessions "
          f"(season {season}) -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "IndyNXT.ics")
