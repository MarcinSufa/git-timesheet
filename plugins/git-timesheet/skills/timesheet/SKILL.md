---
name: timesheet
description: |
  Generate weekly PDF/CSV timesheets from git commit history across one or more repos.
  Hours per day are allocated by commit size; public holidays (US, GB, DE, PL, AU, NZ,
  CA, FR, NL), PTO/sick days, project mapping, saved profiles, custom templates and an
  optional push to Toggl/Clockify/TMetric/Harvest are supported.
  Use when asked to "generate timesheets", "create a timesheet for <dates>", "timesheet
  from my commits", or in Polish "zrób timesheet", "rozliczenie godzin z commitów",
  "raport godzin za tydzień".
argument-hint: "[date range] [profile]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  # Optional, only for template previews or as a last-resort PDF path (references/pdf.md).
  # Plugin installs use the long prefix, standalone MCP servers the short one.
  - mcp__plugin_playwright_playwright__browser_navigate
  - mcp__plugin_playwright_playwright__browser_run_code
  - mcp__plugin_playwright_playwright__browser_take_screenshot
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_run_code
  - mcp__playwright__browser_take_screenshot
---

# Timesheet Generator

Weekly timesheets from git history with realistic time allocation. The logic
lives in tested scripts; this file is the conversation around them.

`S="${CLAUDE_SKILL_DIR}/scripts"` (all stdlib Python 3.9+; on Windows use
`py -3` for `python3`):

| Script | Job |
|---|---|
| `datadir.py` | where profiles/templates live, legacy migration |
| `dates.py` | date menu, presets, working days, ISO weeks |
| `holidays.py` | public holidays (`YEAR CC`) |
| `collect.py` | commits as JSON (author date, numstat, merges skipped) |
| `allocate.py` | hours per entry and day |
| `render.py` | CSV / HTML / PDF files + report JSON + invoice |
| `push_entries.py`, `auth_header.py` | time-tracker push |

## Ground rules

- **Ask in plain markdown text.** Print each question as a numbered/lettered
  list and wait for the reply. Do NOT use `AskUserQuestion`, Plan mode or any
  selection widget: they rewrite the option labels (e.g. replace the
  half-month presets with "Last week").
- **Pre-generation checklist — never skip.** Before `collect.py` or any output,
  all six must be true; otherwise STOP and ask:
  1. the date range came from this invocation (`--range`, date arguments, or
     the answer to the date question) — never from a previous run, today's
     date or the profile;
  2. the resolved range was shown and confirmed;
  3. days off were asked (even for a one-day range);
  4. a profile is loaded or all setup questions were answered;
  5. the commit summary was shown and approved;
  6. output format and template are chosen.
- **Sources of truth:** profile settings, live git history for the range, the
  scripts' output and the user's answers in this session. Sample PDFs,
  imported templates and earlier output are layout only — never copy names,
  projects, dates, hours or Billable values from them.
- **Billable is `Yes` for every entry** unless the profile has
  `settings.billable: "no"`. `examples/sample-timesheet.pdf` shows "No" from
  an old version; ignore it.
- **Tokens** come only from environment variables (references/push.md). Never
  ask for one in chat, never print one (not even a prefix).

## Usage

```
/timesheet                              # interactive
/timesheet 16 Mar to 15 Apr             # date range from arguments
/timesheet --range first-half[:2026-03] # also second-half, full-month, last-month,
                                        # this-week, last-week, or a profile customRange
/timesheet --profile team-acme
/timesheet --save-profile | --list-profiles | --edit-profile NAME | --delete-profile NAME
/timesheet --import-template FILE | --list-templates | --edit-template NAME | --delete-template NAME
/timesheet --push toggl|clockify|tmetric|harvest
```

Profile commands: [references/profiles.md](references/profiles.md).
Template commands: [references/templates.md](references/templates.md).

## Workflow

### 1. Data directory and profile

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/datadir.py" --plugin-data "${CLAUDE_PLUGIN_DATA}" --init
```

Prints `dir`, `profiles`, `templates` and `legacy`. If `legacy` is set (data
from 1.0.x in `~/.claude/skills/timesheet/`), offer to copy it with
`--migrate`. Profiles are `<dir>/profiles/<name>.json`.

- Several profiles and no `--profile` → Question 1 in
  [references/setup.md](references/setup.md).
- No profile → the first-run questions in setup.md, in order, none skipped.

### 2. Date range

Skip the question only when `--range` or date arguments were given. Otherwise
print the menu from `python3 "$S/dates.py" menu --profile <profile>` exactly as
described in [references/dates.md](references/dates.md) (half-month presets;
never "this week"/"last N weeks" unless `preferWeekly`). Resolve presets and
saved names with `dates.py resolve`; normalize free text to ISO yourself
(EU `D.MM` unless the country is US/CA; ask when ambiguous).

### 3. Days off and settings

Ask about days off (setup.md, Question 3) and turn the answer into
`--day-off DATE[..DATE]:pto|sick|holiday[:reason]` values. With a profile, show the
settings summary (Question 4) and loop until approved. Then confirm the range:

```bash
python3 "$S/dates.py" info START END --country CC --day-off ...
```

> Searching commits from **2026-04-01 (Wed)** to **2026-04-15 (Wed)** — both dates inclusive.
> That's 10 working days (Mon-Fri), excluding weekends, public holidays and PTO.
>
> A) Looks correct, continue
> B) Wrong dates — let me re-enter

### 4. Collect commits

Make a work directory once (`mktemp -d`) and write its path literally in later
commands (shell variables do not persist between Bash calls). Per member:

```bash
python3 "$S/collect.py" --since START --until END \
  --author "janedoe" --author "jane@example.com" \
  --repo "/path/to/my-app=my-app" --repo "/path/to/lib=lib" > "$WORK/commits-jane.json"
```

Dates are the commits' author dates, both ends inclusive; merges are skipped
(`--merges` to include), only the checked-out branch is scanned (`--all` for
every branch). A missing repo is reported with `"error"` and skipped. Show the
summary from `repos[]` before going on (MANDATORY):

> Found **23 commits** across **3 repos** for **Jane Doe** (2026-04-01 → 2026-04-15):
>
> | Repo | Commits | Most recent |
> |---|---|---|
> | my-app | **12** | 2026-04-14 |
> | shared-lib | **8** | 2026-04-15 |
>
> A) Yes, continue
> B) Add more author patterns / repos
> C) Adjust date range
> D) I expected commits in a repo that aren't shown — investigate

For D run `collect.py --list-authors` with the same range and repos and show
the authors, so the user can spot a missing email or name.

### 5. Allocate

```bash
python3 "$S/allocate.py" --commits "$WORK/commits-jane.json" --profile <profile> \
  --member "Jane Doe" --start START --end END --day-off ... > "$WORK/alloc-jane.json"
```

Without a profile pass `--hours-per-day`, `--increment`, `--work-days`,
`--country`, `--allow-overtime --max-hours-per-day`. Rules and the choices
behind them: [references/allocation.md](references/allocation.md).

- `needs_input` lists working days of weeks with no commits: ask what the user
  worked on, add the entries as described in allocation.md and run again.
- Show `warnings` (e.g. merged entries) to the user.

### 6. Render

```bash
python3 "$S/render.py" --allocation "$WORK/alloc-jane.json" --profile <profile> \
  --plugin-data "${CLAUDE_PLUGIN_DATA}" --format pdf|csv|html|both --out-dir ~/Downloads
```

Flags override the profile (`--lang`, `--time-format`, `--date-format`,
`--template`, `--billable`, `--filename-pattern`). It prints a JSON report.
Exit code 3 means no PDF engine worked: the HTML and CSV are kept and the
message says what to install — see [references/pdf.md](references/pdf.md)
(including the optional Playwright MCP path). Formats, CSV columns and time
formats: [references/output.md](references/output.md). Languages:
[references/i18n.md](references/i18n.md).

### 7. Report and invoice

Report the files per week (entries, total, work days, days off) as in
output.md, then offer the invoice summary (billable hours × rate) described
there. If the user chose to save the profile, confirm its path.

### 8. Push (optional)

Only with `--push` or `settings.pushTo`, after explicit confirmation. Follow
[references/push.md](references/push.md): `auth_header.py --check`, project ID
lookup, `push_entries.py --service ...`, `curl -H @"$HDR" -d @payload`.

### 9. Clean up

Delete the work directory, any HTML kept only for PDF conversion, a local
HTTP server you started and `.playwright-mcp/` files. Never delete the user's
output files or profiles.

## Edge cases

- **Full PTO week:** all days PTO, 0:00 total, no question needed.
- **Sick day with commits:** stays sick; the work moves to the nearest
  working day.
- **Multiple members:** collect, allocate and render per member.
- **Country without a built-in calendar:** `holidays.py` prints a notice and
  no holidays; ask for the dates and pass `--day-off DATE:holiday:Name`.
- **NZ after 2030:** the scripts stop with an error (Matariki dates are
  published only through 2030); ask for the holidays and rerun with
  `--country none` plus `--day-off DATE:holiday:Name`.
- **Repo not found on disk:** warn and continue with the other repos.
