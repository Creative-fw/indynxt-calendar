#!/usr/bin/env python3
"""
Indy NXT -> auto-updating ICS feed.

Source: the schedule page at indynxt.com (server-rendered HTML; no public
API, official calendar is account-gated ECAL, downloadable schedule is PDF).
The page's event cards are parsed with class-anchored regexes.

- Race-only feed (the schedule page publishes race slots only)
- Times are listed in US Eastern Time -> converted via zoneinfo (DST-aware)
- 'TBD' times become all-day events until the source publishes a time;
  the daily sync upgrades them automatically
- Season year is read from the page's own event links, so the feed rolls
  to the new season when the site does
- Abort guard keeps the feed stale-but-valid if the site is ever redesigned
"""
import html
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

URL = "https://www.indynxt.com/schedule"
ET = ZoneInfo("America/New_York")
MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
MIN_EVENTS = 10
RACE_MINUTES = 60
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


def esc(x):
    return x.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


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

    rows.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    season = rows[0][0]
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//LGS//IndyNXT Auto-Sync//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:Indy NXT",
             f"X-WR-CALDESC:INDY NXT by Firestone (season {season}) - all races\\, "
             "auto-synced daily from indynxt.com",
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
    lines.append("END:VCALENDAR")

    with open(out_path, "w", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")
    print(f"OK: wrote {len(rows)} events (season {season}) -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "IndyNXT.ics")
