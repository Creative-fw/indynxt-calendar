# Indy NXT Calendar Feed

Auto-updating ICS calendar for **INDY NXT by Firestone** — races **plus practice and qualifying**.

## Subscribe

```
https://raw.githubusercontent.com/Creative-fw/indynxt-calendar/main/IndyNXT.ics
```

Subscribe (don't import) in Apple Calendar / Google Calendar. Calendar name: **Indy NXT**.

## What you get

- **Races** (flagged 🏁): every round, timed from the schedule page; TBD times show as all-day until the site publishes them.
- **Practice / qualifying** (silent): parsed from each round's detail page weekend schedule, 45-minute blocks.

## How it works

- `indynxt_sync.py` runs daily (05:00 UTC) via GitHub Actions and commits `IndyNXT.ics` if changed.
- Races come from the schedule page's event cards; sessions come from each round page's `schedule-table` (day headers + time/description entries). Non-race `INDY NXT - *` entries are kept; doubleheader pages repeat the weekend schedule, so sessions dedupe by (date, time, name).
- All source times are US Eastern, converted via zoneinfo (DST-aware). Rounds whose schedules aren't published yet gain sessions automatically once indynxt.com posts them.
- Round-page fetch failures are non-fatal; an abort guard protects the race backbone if the site is redesigned.
