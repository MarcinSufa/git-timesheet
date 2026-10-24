# Output formats, report and invoice

## Files

One file per ISO week (Mon-Sun) per member, named by `filenamePattern`
(default `Timesheet_{member}_Weekly_{startDate}_{endDate}`, dates `YYYYMMDD`,
clipped to the requested range). `render.py` formats:

- `pdf` — the filled template printed by headless Chromium ([pdf.md](pdf.md));
- `csv` — importable to tmetric / Toggl / spreadsheets;
- `html` — the filled template only (preview, or PDF via another tool);
- `both` — PDF + CSV.

Grid rules: every working day totals exactly the configured hours (more only
with overtime, then the day total is red); weekends show `-`; holidays show
"Holiday: {name}", PTO "PTO", sick days "Sick", each with no hours; entries
with no time on a day show `-`.

## CSV

```csv
User,Time Entry,Task,Project,Billable,Tags,Work Type,Link,2026-03-30,...,2026-04-05,Total
Jane Doe,feat(auth): Add login,,My App,Yes,,,,5:45,-,...,-,5:45
```

ISO dates as day headers; holiday/PTO/sick columns show the reason instead of
`-`; `Project` is the mapped project or "No project". The header row is always
English (importers rely on it).

## Time formats (`timeFormat`)

- `H:MM` (default): `5:30`, `0:45`.
- `decimal`: `5.5`, `0.75` (always a multiple of the increment).
- `HH:MM:SS`: `05:30:00`, `00:45:00`.
- `AM/PM`: each cell shows `9:00 AM - 11:45 AM`; tasks of a day run back to
  back from `dayStartTime` (default 09:00) and the lunch break
  (`lunchBreak`, default 12:00-13:00) is skipped, so a task that crosses lunch
  ends one hour later. Totals stay durations (`H:MM`).

Date formats (`dateFormat`): `D MMM YYYY` (3 Mar 2026), `MMM D, YYYY`,
`DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY-MM-DD`; month names follow the language.

## Report (Step 7)

Build it from `render.py`'s JSON (`weeks[]`: file names, entries, total,
work_days, days_off):

```
Generated 4 timesheets for Jane Doe:

  Timesheet_Jane_Doe_Weekly_20260216_20260222.pdf
   6 entries | 40:00 total | 5 work days

  Timesheet_Jane_Doe_Weekly_20260223_20260301.pdf
   5 entries | 32:00 total | 4 work days
   Wed 25 Feb — PTO

Days off in this period:
   Wed 25 Feb — PTO
   No public holidays in this range

Profile used: my-profile
```

Add any `warnings` from `allocate.py`/`render.py` and, if the profile was
saved, its full path.

## Invoice summary (optional)

Ask:

> Do you want an invoice summary (total hours × hourly rate)?
>
> A) Yes
> B) No

If yes: offer the profile's `invoicing.hourlyRate`/`currency` (*"Use saved
rate **85.00 USD/hr**? A) Yes B) No, enter a different rate"*), otherwise ask
*"What's your hourly rate? Enter as `<amount> <currency-code>`, e.g. `85 USD`,
`350 PLN`, `70 EUR`"*. Run `render.py` with `--rate` / `--currency` (or read
the `invoice` object it printed: billable hours only, amount rounded to 2
decimals) and show:

> **Invoice Summary** (2026-04-01 → 2026-04-15):
>
> | Metric | Value |
> |---|---|
> | Weeks included | 3 |
> | Total hours | 120:00 (120.00 h) |
> | Hourly rate | 85.00 USD |
> | **Total payment** | **10,200.00 USD** |

Use the user's locale for thousands separators. If the rate was typed, offer
to save it to the profile's `invoicing`.
