# Profiles

## Where profiles live

`scripts/datadir.py` decides, in this order:

1. `$GIT_TIMESHEET_HOME`, if set (e.g. a synced folder);
2. the plugin's persistent data directory, `${CLAUDE_PLUGIN_DATA}` (Claude Code
   sets it for installed plugins; it survives plugin updates);
3. `${XDG_CONFIG_HOME:-~/.config}/git-timesheet` (skill installed by hand, or
   Claude Code without `CLAUDE_PLUGIN_DATA`).

```
<data dir>/
├── profiles/   my-profile.json, team-acme.json, ...
└── templates/  company-x.html, ...  (the built-in "default" is not here)
```

Up to 1.0.4 the data lived in `~/.claude/skills/timesheet/`. When that folder
still has profiles or templates, `datadir.py` reports it as `legacy`; ask
before running `datadir.py --plugin-data "${CLAUDE_PLUGIN_DATA}" --migrate`,
which copies (never overwrites, never deletes) into the new location.

Profiles hold no secrets (tokens live in environment variables, see
[push.md](push.md)) but they do hold local paths and names: do not commit them.

## Schema

```json
{
  "name": "my-profile",
  "members": [
    {
      "displayName": "Jane Doe",
      "gitAuthors": ["janedoe", "Jane", "jdoe"],
      "repos": [
        { "path": "/home/jane/projects/my-app", "label": "my-app" },
        { "path": "/home/jane/projects/shared-lib", "label": "shared-lib" }
      ]
    }
  ],
  "settings": {
    "hoursPerDay": 8,
    "workDays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "timeIncrement": 15,
    "country": "US",
    "outputFormat": "pdf",
    "outputDir": "~/Downloads",
    "filenamePattern": "Timesheet_{member}_Weekly_{startDate}_{endDate}",
    "allowOvertime": false,
    "maxHoursPerDay": 10,
    "template": "default",
    "billable": "yes",
    "timeFormat": "H:MM",
    "dateFormat": "D MMM YYYY",
    "language": "en",
    "preferWeekly": false,
    "dayStartTime": "09:00",
    "lunchBreak": { "start": "12:00", "end": "13:00" },
    "pushTo": null
  },
  "projectMapping": {
    "my-app": {
      "default": "My App",
      "scopes": { "auth": "My App - Auth", "api": "My App - Backend" }
    },
    "shared-lib": { "default": "Shared Library" }
  },
  "customRanges": {
    "biweekly-1": { "monthDays": [1, 14] },
    "biweekly-2": { "monthDays": [15, "last"] },
    "fiscal-q1":  { "monthRange": ["jan", "mar"] },
    "prev-week":  { "weekOffset": -1 }
  },
  "invoicing": { "hourlyRate": 85.00, "currency": "USD" }
}
```

Notes:

- `country`: `US GB DE PL AU NZ CA FR NL`, `"none"` for no holidays, or any
  other code (no built-in calendar; see setup.md).
- `outputFormat`: `pdf`, `csv`, `html` or `both` (PDF + CSV).
- `timeFormat`: `H:MM`, `decimal`, `HH:MM:SS` or `AM/PM`. `dayStartTime` and
  `lunchBreak` are used only with `AM/PM`.
- `template`: `default`, the name of a file in `<data dir>/templates/`, or a path.
- `billable`: `"yes"` (default) or `"no"`.
- `filenamePattern`: `{member}`, `{startDate}`, `{endDate}` (dates as `YYYYMMDD`).
- `projectMapping` keys are repo labels; unmapped entries show "No project".
- `pushTo`: `null` or `{ "service": "toggl", "workspaceId": "123456" }`
  (Clockify: `workspaceId`; TMetric: `accountId`; Harvest: none — the account
  ID is an environment variable). Never a token.
- Profiles never store dates: the range is asked on every run.

`allocate.py --profile` reads `settings` and `projectMapping`;
`render.py --profile` reads `settings` and `invoicing`;
`dates.py --profile` reads `customRanges` and `settings.preferWeekly`.
Members and repos are passed to `collect.py` as flags.

## Management commands

These never generate timesheets; they only change saved configuration.

### `--list-profiles`

Read every profile and show a summary table:

> Saved profiles (3):
>
> | Profile | Members | Repos | Hours/day | Country | Format | Template |
> |---|---|---|---|---|---|---|
> | my-profile | Jane Doe | 3 | 8h | US | PDF | default |
> | team-acme | 4 members | 5 | 8h | US | Both | acme-template |
> | freelance | Jane Doe | 2 | 6h | US | CSV | — |

If there are none, say so and offer `--save-profile`.

### `--edit-profile <name>`

> Editing profile **my-profile**. What do you want to change?
>
> A) Members / git authors
> B) Repositories
> C) Hours per day, work days, time increment
> D) Country (holidays)
> E) **Output format and template** (reuses the combined Output format question)
> F) Output directory and filename pattern
> G) Time format / date format / language
> H) Project mapping
> I) Push integration (Toggl / Clockify / TMetric / Harvest)
> J) Invoicing (hourly rate + currency)
> K) Custom ranges (named date presets like `biweekly-1`, `fiscal-q1`)
> L) Billable default (mark all entries billable: yes / no)
> M) Done — save and exit

Ask the questions from [setup.md](setup.md) for the chosen section. After each
edit ask *"anything else to change?"* and loop until the user picks **M**, then
write the JSON back.

### `--delete-profile <name>`

> Delete profile **my-profile**? This is permanent.
>
> A) Yes, delete it
> B) No, keep it

A: delete the file. B: do nothing.
