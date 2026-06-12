# Indy NXT Calendar Feed (auto-updating)

Auto-syncing ICS subscription feed for **INDY NXT by Firestone** — IndyCar's official feeder series.

## Subscribe (don't import)

```
https://raw.githubusercontent.com/Creative-fw/indynxt-calendar/main/IndyNXT.ics
```

Apple Calendar (Mac): File → New Calendar Subscription → paste URL.
iPhone: Settings → Apps → Calendar → Calendar Accounts → Add Account → Other → Add Subscribed Calendar.

**Never double-click / import the .ics** — that creates a static one-off copy that never updates.

## What's inside

- **All races, race-only feed** (~17 events per season; the source publishes race slots only)
- Every race flagged 🏁 — **silent feed, no alarms** (feeder-series treatment)
- 60-minute race blocks; venue in LOCATION, official race name in DESCRIPTION
- Races with **TBD times appear as all-day events** and upgrade automatically when a time is published
- Times auto-convert from US Eastern to your local timezone

## How it works

A GitHub Action runs daily at 05:00 UTC (09:00 Dubai). No public API exists for Indy NXT —
the official "Add to Calendar" is an account-gated ECAL widget and the downloadable schedule is a PDF —
so the script **scrapes the server-rendered schedule page** on indynxt.com with class-anchored
parsing. The season year is read from the page's own event links, so the feed rolls to the new
season when the site does. An abort guard (<10 events) keeps the feed stale-but-valid if the
site is ever redesigned.

## Sister feeds

- [IndyCar](https://github.com/Creative-fw/indycar-calendar) · [F1](https://github.com/Creative-fw/f1-2026-calendar) · [F2 + F3](https://github.com/Creative-fw/f2-f3-calendar) · [MotoGP](https://github.com/Creative-fw/motogp-calendar) · [Formula E](https://github.com/Creative-fw/formula-e-calendar) · [WEC](https://github.com/Creative-fw/wec-2026-calendar) · [ELMS](https://github.com/Creative-fw/elms-2026-calendar) · [MLMC](https://github.com/Creative-fw/mlmc-2026-calendar)
