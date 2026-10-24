# Date range: menu, presets and free-text dates

`scripts/dates.py` computes everything on this page. All results are ISO dates
(`YYYY-MM-DD`), both bounds inclusive.

## The menu (Question 2)

Get the options from the script, never compute them by hand:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/dates.py" menu [--profile "<profile.json>"]
```

It returns `today`, `weekday` and three `options` (`label`, `start`, `end`).
Print exactly this structure as plain markdown (no `AskUserQuestion`):

```
Today is **{today}** ({weekday}).

Which date range?

1. **{options[0].label}** — {options[0].start} → {options[0].end}
2. **{options[1].label}** — {options[1].start} → {options[1].end}
3. **{options[2].label}** — {options[2].start} → {options[2].end}
4. **Custom** — I'll type the dates

Reply with `1`, `2`, `3`, or `4` — or type a date range directly (e.g., `1 Apr to 15 Apr`, `1.04 to 15.04`, or a saved range name like `biweekly-1`).
```

How the script picks the options (for reference):

- Day of month > 15: `Second half of this month`, `First half of this month`.
- Day of month ≤ 15: `First half of this month`, `Second half of last month`.
- Option 3: the first entry of `profile.customRanges`, otherwise `Last month`.
- Only when `profile.settings.preferWeekly` is `true`: options 1-2 become
  `This week` / `Last week`. The flag is not set by default.

### Options you MUST NOT include

Never replace options 1-3 with "This week", "Last week", "Last N weeks",
"Month to date" or "Last 30 days". Weekly and rolling ranges do not align with
invoice cycles; the half-month preset is the dominant case. A user who wants a
weekly range types it via option 4 (or sets `preferWeekly`).

### Parsing the reply

- `1`, `2`, `3` → that option's dates; go to the confirmation step.
- `4` → ask: *"Type the range (e.g., `1 Apr to 15 Apr`, `1.04 to 15.04`, `2026-04-01 to 2026-04-15`, or a saved range name like `biweekly-1`):"*
- A free-text range → normalize it (below).
- A saved range name → `dates.py resolve <name> --profile <profile.json>`.
- Anything unclear → reprint the menu with *"I didn't understand — reply with `1`, `2`, `3`, `4`, or type a date range directly."*

## Presets (`--range NAME` or `dates.py resolve NAME`)

| Name | Resolves to | Offset |
|---|---|---|
| `first-half` | 1st → 15th of the current month | `:2026-03`, `:march`, `:mar` |
| `second-half` | 16th → last day of the current month | same |
| `full-month` | 1st → last day of the current month | same |
| `last-month` | the whole previous month | none |
| `this-week` | Mon → Sun of the current ISO week | none |
| `last-week` | Mon → Sun of the previous ISO week | none |

Custom ranges from `profile.customRanges` resolve the same way:

| Type | Schema | Resolution |
|---|---|---|
| `monthDays` | `{ "monthDays": [1, 14] }` | days of the current month; `"last"` = last day |
| `monthRange` | `{ "monthRange": ["jan", "mar"] }` | 1st of the first month → last day of the second, current year |
| `weekOffset` | `{ "weekOffset": -1 }` | ISO week relative to the current one (0 = this week) |

## Free-text dates

Normalize to ISO before anything else. Never assume US `MM/DD/YYYY`.

| User input | ISO |
|---|---|
| `1 Apr to 15 Apr` | `<year>-04-01` to `<year>-04-15` |
| `1.04 to 15.04` | `<year>-04-01` to `<year>-04-15` (EU `D.MM`) |
| `01.04.2026 - 15.04.2026` | `2026-04-01` to `2026-04-15` |
| `01/04/2026 - 15/04/2026` | EU: `2026-04-01` to `2026-04-15` |
| `4/1/2026 - 4/15/2026` | US: `2026-04-01` to `2026-04-15` |
| `2026-04-01 to 2026-04-15` | already ISO |

- If the profile `country` is not `US` or `CA`, read ambiguous numeric dates as EU (`D.MM`, `DD.MM.YYYY`).
- Confirm genuinely ambiguous input such as `1/4/2026`: *"I'm reading this as 1 April 2026 — correct?"*
- A date without a year is in the current year.

## Confirmation (MANDATORY)

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/dates.py" info START END --country CC [--work-days Mon,Tue,...] [--day-off ...]
```

It returns the weekdays of both ends, `working_days` (after holidays and the
days off passed in) and the ISO `weeks` (one timesheet per week and member).
Show:

> Searching commits from **2026-04-01 (Wed)** to **2026-04-15 (Wed)** — both dates inclusive.
> That's 10 working days (Mon-Fri), excluding weekends, public holidays and PTO.
>
> A) Looks correct, continue
> B) Wrong dates — let me re-enter
