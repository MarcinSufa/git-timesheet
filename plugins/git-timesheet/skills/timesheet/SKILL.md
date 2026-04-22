---
name: timesheet
version: 1.0.4-beta
description: |
  Generate weekly PDF/CSV timesheets from git commit history across multiple repos.
  Allocates hours per day based on commit complexity (lines changed, files touched).
  Supports public holidays by country, PTO/sick days, multiple team members,
  project mapping, saved profiles, custom templates, and configurable work hours.
  Use when asked to "generate timesheets", "create timesheet", or "timesheet for <dates>".
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  # Playwright tools are optional — needed only for PDF output.
  # If unavailable, the skill falls back to CSV-only output.
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_run_code
  - mcp__playwright__browser_take_screenshot
  - mcp__playwright__browser_snapshot
---

# Timesheet Generator

Generate weekly timesheets from git history with realistic time allocation.

## Saved Profiles

Profiles are stored in `~/.claude/skills/timesheet/profiles/`. Each profile is a JSON file:

```
~/.claude/skills/timesheet/profiles/
├── my-profile.json       # personal profile
├── team-acme.json        # multi-member profile
└── ...
```

### Profile schema

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
    "pushTo": null
  },
  "projectMapping": {
    "my-app": {
      "default": "My App",
      "scopes": {
        "auth": "My App - Auth",
        "api": "My App - Backend"
      }
    },
    "shared-lib": {
      "default": "Shared Library"
    }
  },
  "customRanges": {
    "biweekly-1": { "monthDays": [1, 14] },
    "biweekly-2": { "monthDays": [15, "last"] },
    "fiscal-q1":  { "monthRange": ["jan", "mar"] }
  },
  "invoicing": {
    "hourlyRate": 85.00,
    "currency": "USD"
  }
}
```

### Profile loading

On startup:

1. Check if `~/.claude/skills/timesheet/profiles/` exists
2. If profiles exist, list them and ask which to use (or create new)
3. If no profiles exist, run the full interactive setup and offer to save as a profile

```bash
ls ~/.claude/skills/timesheet/profiles/*.json 2>/dev/null
```

### Custom Templates (from user-provided examples)

Users can provide a PDF, image (PNG/JPG), or DOCX of their existing timesheet to match that format.
Templates are stored alongside profiles:

```
~/.claude/skills/timesheet/templates/
├── default.html       # built-in tmetric-style template
├── company-x.html     # generated from user's PDF example
└── ...
```

Template profile field:
```json
{
  "settings": {
    "template": "default"
  }
}
```

## Usage

```
/timesheet                              # interactive — loads profile or asks questions
/timesheet 16 Mar to 15 Apr             # uses default profile, date range from args
/timesheet --range first-half           # preset: 1st-15th of current month
/timesheet --range second-half          # preset: 16th-end of current month
/timesheet --range full-month           # preset: 1st-end of current month
/timesheet --range last-month           # preset: 1st-end of previous month
/timesheet --range this-week            # preset: Mon-Sun of current week
/timesheet --range last-week            # preset: Mon-Sun of previous week
/timesheet --range first-half:2026-03   # preset with offset: Mar 1-15, 2026
/timesheet --range biweekly-1           # custom range from profile.customRanges
/timesheet --profile team-acme          # use specific profile
/timesheet --save-profile               # run setup and save as new profile
/timesheet --edit-profile my-profile    # edit existing profile (incl. template choice)
/timesheet --list-profiles              # list all saved profiles
/timesheet --delete-profile my-profile  # delete a saved profile (with confirmation)
/timesheet --import-template myfile.pdf # create template from example file
/timesheet --list-templates             # list all saved templates
/timesheet --edit-template company-x    # refine a saved template via natural language
/timesheet --delete-template company-x  # delete a saved template (with confirmation)
/timesheet --push toggl                 # generate + push to Toggl Track
/timesheet --push clockify              # generate + push to Clockify
/timesheet --push tmetric               # generate + push to TMetric
/timesheet --push harvest               # generate + push to Harvest
```

## Management Commands

These commands manage saved profiles and templates outside the normal generation flow. They never produce timesheets — they only modify saved configuration.

### `--list-profiles`

Read every `*.json` file in `~/.claude/skills/timesheet/profiles/` and show a summary table:

> Saved profiles (3):
>
> | Profile | Members | Repos | Hours/day | Country | Format | Template |
> |---|---|---|---|---|---|---|
> | my-profile | Jane Doe | 3 | 8h | US | PDF | default |
> | team-acme | 4 members | 5 | 8h | US | Both | acme-template |
> | freelance | Jane Doe | 2 | 6h | US | CSV | — |

If no profiles exist, say so and offer to create one with `--save-profile`.

### `--edit-profile <name>`

Load the profile and present a menu of editable sections. The user picks one (or sequentially picks several), gets prompted for the new value(s), then the profile is rewritten.

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

After each edit, ask *"anything else to change?"* and loop until the user picks J. Then write the updated JSON back to the profile file.

### `--delete-profile <name>`

Confirm explicitly before deletion:

> Delete profile **my-profile**? This is permanent.
>
> A) Yes, delete it
> B) No, keep it

If A: remove the file. If B: do nothing.

### `--list-templates`

Read every `*.html` file in `~/.claude/skills/timesheet/templates/`. The built-in **default** template is always shown first.

> Saved templates (3):
>
>   - **default** — built-in, read-only
>   - **company-x** — imported 2026-04-22 from `our-timesheet.pdf`
>   - **acme-template** — imported 2026-03-10 from `acme.docx`

If Playwright MCP is available, render a small thumbnail preview of each template (one sample week of data) so the user can recognize them visually.

### `--edit-template <name>`

Refine an existing template via natural language. Read the current `<name>.html`, render it as a screenshot for visual context, then ask:

> Current template **company-x**:
> [render the template via Playwright and show the screenshot]
>
> What do you want to change? Describe in plain English. Examples:
>
>   - "make the header bigger and bold"
>   - "switch to A4 portrait"
>   - "remove the Billable column"
>   - "change the brand color to #0055AA"
>   - "add the company logo at top-right" (then ask for the image path)

Apply the change to the HTML, render the updated template, and show before/after side by side. Ask:

> A) Looks good, save
> B) Needs more adjustment (describe)
> C) Revert and start over

Loop on B until the user picks A. The built-in **default** template cannot be edited — instead, copy it to a new name first.

### `--delete-template <name>`

Confirm explicitly. The built-in **default** template cannot be deleted.

> Delete template **company-x**? This is permanent and cannot be undone.
> Profiles still referencing this template will fall back to **default** until updated.
>
> A) Yes, delete it
> B) No, keep it

If A: remove the file. Optionally: scan all profiles, find any that reference the deleted template, and offer to update them.

## Workflow

### CRITICAL: Pre-Generation Checklist — NEVER SKIP

Before writing any HTML, PDF, CSV, or running any `git log` command, **all six** of the following MUST be true. No exceptions — not for "same profile as last time", not for "obviously the user wants the previous range", not for any other reason. Lack of explicit user input on any of these is a STOP condition.

1. **Date range obtained from explicit user input on this invocation.**
   - Acceptable sources: `--range <name>` flag, positional date args (e.g., `/timesheet 16 Mar to 15 Apr`), OR the user's answer to Question 2 in this session.
   - **NOT acceptable:** dates from the previous run, today's date, the saved profile (profiles do not store dates), or any inference from context.
   - If `/timesheet` is invoked with no flags and no positional date args, you **MUST** ask Question 2.

2. **Date range confirmation shown and approved by the user.** (Step 2's confirmation step.)

3. **PTO/days off asked.** (Question 3 — ask even if user picked a single-day range.)

4. **Profile loaded OR all setup questions answered.**

5. **Commit count summary shown and approved by the user.** (Step 3's MANDATORY summary table.)

6. **Output format and template chosen.** (Combined Output format question.)

**If any item is missing, STOP and ask the user. Never assume.** The single most common skill failure is silently regenerating with last-run defaults — this checklist exists to prevent that.

### Step 0: Interactive Setup

**ALL user interaction in this skill happens via plain markdown text in chat. Do NOT use the `AskUserQuestion` tool, Plan mode, or any UI selection widget.** Print each question as a numbered or lettered markdown list in a chat message, then wait for the user to reply with their selection (a number, letter, or free text). This rule overrides Claude's default preference for `AskUserQuestion`.

Why text-only? Because `AskUserQuestion` reformats option labels — it has repeatedly substituted our specified half-month presets with "Last week / This week / Last N weeks", which breaks the invoicing UX. Plain chat text gives us pixel-exact control over what the user sees.

Skip a question when its answer comes from a loaded profile or CLI args; otherwise ask.

**Question 0 — Template Import** (only if `--import-template` given or user mentions a file):

If the user provides a PDF, image, or DOCX as a timesheet example:

1. **Read the file** using the `Read` tool (supports PDF, images, DOCX)
2. **Analyze the layout** — identify:
   - Column structure (what columns exist, their order)
   - Header format (logo, company name, period display style)
   - Row format (how time entries are displayed)
   - Day columns (format: dates, day names, abbreviations)
   - Totals row (position, styling)
   - Color scheme and fonts
   - Special labels (billable, projects, tags, work type)
   - Any branding elements (logos, company colors)
3. **Generate an HTML template** that replicates the layout as closely as possible
4. **Save the template** to `~/.claude/skills/timesheet/templates/<name>.html`
5. **Show a preview** — generate one sample week and open in Playwright for user to verify
6. **Ask for adjustments** until the user approves

```
> I've analyzed your timesheet example and created a template.
> Here's a preview — does this match your format?
>
> A) Perfect, save it!
> B) Needs adjustments (I'll describe what to change)
> C) Start over with a different approach
```

Template analysis checklist:
- [ ] Logo position and style (top-left, top-right, centered?)
- [ ] Title text and font size
- [ ] Header metadata (member name, period, total — layout and labels)
- [ ] Table structure (columns, widths, alignment)
- [ ] Day header format (Mon/Tue vs Monday/Tuesday, date format)
- [ ] Time format (H:MM, decimal like 5.5, or HH:MM:SS)
- [ ] Empty cell representation (dash, blank, 0:00?)
- [ ] Color scheme (header bg, borders, text colors, alternating rows?)
- [ ] Footer content (page numbers, signatures, notes?)
- [ ] Page orientation and size (A4 landscape, Letter portrait, etc.)

**Question 1 — Profile Selection** (skip if `--profile` given or only one profile exists):
> Found saved profiles:
>
> A) **my-profile** — Jane Doe (my-app, shared-lib) [US, 8h/day, PDF]
> B) **team-acme** — 3 members (my-app, shared-lib) [US, 8h/day, PDF]
> C) Create new profile
> D) One-time run (no profile)

**Question 2 — Date Range — MANDATORY unless explicit args on this invocation.**

**SKIP this question ONLY if one of these is true:**
- User invoked with `--range <name>` flag (e.g., `/timesheet --range second-half`)
- User invoked with positional date args (e.g., `/timesheet 16 Mar to 15 Apr`)

Otherwise ALWAYS ask — do not skip because a profile is loaded, because last run's dates seem obvious, or because today's date "implies" a range.

### ⚠️ DO NOT use `AskUserQuestion` for this question.

Prior testing showed `AskUserQuestion` consistently reformats or substitutes option labels — it replaces half-month presets with "Last week", "This week", "Last N weeks", or "Last 4 weeks". For this question only, **bypass `AskUserQuestion` entirely and print the menu as plain markdown in the chat**, then wait for the user to reply with a number or text.

### The menu — print exactly this structure

Print the following in chat as plain markdown (substitute `{...}` placeholders with actual dates computed from today):

```
Today is **{today-iso}** ({today-dayname}).

What date range do you want timesheets for?

1. **{Option 1 label}** — {Option 1 dates}
2. **{Option 2 label}** — {Option 2 dates}
3. **{Option 3 label}** — {Option 3 dates}
4. **Custom** — I'll type the dates

Reply with `1`, `2`, `3`, or `4` — or type a date range directly (e.g., `1 Apr to 15 Apr`, `1.04 to 15.04`, or a saved range name like `biweekly-1`).
```

### How to compute options 1, 2, 3

**If today's day-of-month > 15** (second half of month in progress):
- Option 1 label: `Second half of this month` — dates: 16th → last day of current month
- Option 2 label: `First half of this month` — dates: 1st → 15th of current month
- Option 3: if `profile.customRanges` has entries, use the first one as label + dates. Otherwise: label `Last month`, dates = 1st → last day of previous month.

**If today's day-of-month ≤ 15** (first half of month in progress):
- Option 1 label: `First half of this month` — dates: 1st → 15th of current month
- Option 2 label: `Second half of last month` — dates: 16th → last day of previous month
- Option 3: if `profile.customRanges` has entries, use the first one. Otherwise: label `Last month`.

### Options you MUST NOT include

Regardless of context, the menu above is the only structure. NEVER replace any of options 1-3 with:

- "This week" / "Current week"
- "Last week" / "Previous week"
- "Last N weeks" (for any N)
- "Current month so far" / "Month to date"
- "Last 30 days" or similar rolling windows

Weekly and rolling ranges do not align with invoice cycles. This skill is primarily used for invoicing, and the half-month preset is the dominant case. If the user wants a weekly range, they can type it via option 4.

**Override:** the only time you may substitute weekly presets for options 1-2 is when `profile.settings.preferWeekly === true`. This flag is NOT set by default.

### Parsing the user's reply

- `1`, `2`, or `3` → use that option's pre-resolved dates; proceed to the confirmation step in Step 2
- `4` → ask: *"Type the range (e.g., `1 Apr to 15 Apr`, `1.04 to 15.04`, `2026-04-01 to 2026-04-15`, or a saved range name like `biweekly-1`):"*
- Free-text date range (e.g., `1.04 to 15.04`) → parse directly as custom
- Saved range name (e.g., `biweekly-1`) → resolve via `profile.customRanges`
- Unclear reply → reprint the menu with: *"I didn't understand — reply with `1`, `2`, `3`, `4`, or type a date range directly."*

**Question 3 — PTO / Days Off** (always ask):
> Any days off in this period? (PTO, sick days, personal leave)
>
> A) No days off
> B) Yes — I'll list them (e.g., "3 Mar PTO, 7 Mar sick")
> C) Yes — full weeks off (e.g., "week of 10 Mar")

Parse the user's input into a list of `{ date, reason }` entries.

**Question 4 — Settings Confirmation** (skip if profile loaded, show summary):
> Using profile **my-profile**:
>
> - **Name:** Jane Doe
> - **Hours/day:** 8 (15-min increments)
> - **Work days:** Mon-Fri
> - **Holidays:** United States (US)
> - **Format:** PDF
> - **Repos:** my-app, shared-lib
> - **Days off:** 3 Mar (PTO), 7 Mar (sick)
>
> A) Looks good, generate!
> B) I need to change something (country, repos, format, hours, days off, billable, hourly rate, …)

If user picks **B**:
- If they typed what they want to change in the same message (e.g., *"I want a different PDF format"* or *"change country to US"*), handle that single item directly, then re-show the summary.
- If they only said "B" with no specifics, show this menu and let them pick:
  > Which setting do you want to change?
  >   1. Members / git authors
  >   2. Repositories
  >   3. Hours per day, work days, time increment
  >   4. Country (holidays)
  >   5. Output format and PDF template
  >   6. Output directory / filename pattern
  >   7. Time format / date format / language
  >   8. Project mapping
  >   9. Billable default (yes / no)
  >  10. Invoicing (hourly rate + currency)
  >  11. Push integration (Toggl / Clockify / TMetric / Harvest)
  >  12. Days off (PTO / sick days for this run only)
  >  13. Done — back to summary

After the change, **always re-show the updated summary and ask A/B again** so the user can keep tweaking or confirm. Loop until A.

If no profile, the following questions are **MANDATORY** — ask each one in order as a plain markdown chat message (NOT `AskUserQuestion`). Do not infer, default, or skip any answer (even if the intent seems obvious from context). The user wants explicit control over every setting on first run:

**Your name:**
> What name should appear on the timesheets?

**Git author patterns:**
> What git author name(s) or email(s) should I search for?
> (comma-separated, e.g., "janedoe, Jane Doe, user@example.com")

**Repositories:**
> Which git repositories should I scan?
> Provide absolute paths, one per line. Press Enter twice when done.

**Hours per day:**
> How many hours per work day?
> A) 8h  B) 7.5h  C) 7h  D) 6h  E) Custom

**Time rounding:**
> Time rounding increments?
> A) 15 minutes (e.g., 2:15, 5:45)
> B) 30 minutes (e.g., 2:30, 5:30)
> C) 1 hour (e.g., 2:00, 5:00)

**Country holidays:**
> Which country's public holidays should I exclude?
>
> A) United States (US)
> B) United Kingdom (GB)
> C) Germany (DE)
> D) Poland (PL)
> E) Australia (AU)
> F) New Zealand (NZ)
> G) Canada (CA)
> H) France (FR)
> I) Netherlands (NL)
> J) No holidays — count all weekdays
> K) Other (I'll type the country code)

**Output format + PDF template (combined question):**

This combines output format with PDF template selection so users discover the custom-template feature without needing to know the `--import-template` flag.

Build the choices dynamically — only include the "use saved template" choice(s) if files exist in `~/.claude/skills/timesheet/templates/`:

> What format do you want the timesheets in?
>
> A) PDF — default template (clean weekly grid, tmetric-style)
> B) PDF — match my company's format (I'll provide a sample PDF/PNG/JPG/DOCX)
> C) PDF — use saved template: `<one option per saved .html file>`
> D) CSV (importable to tmetric / Toggl / spreadsheets)
> E) Both PDF (default template) and CSV

**If user picks B**, immediately ask:

> Drop the file path to your timesheet example (PDF, PNG, JPG, or DOCX):

Then run the template-import flow from **Question 0** above: analyze layout, generate matching HTML, save to `~/.claude/skills/timesheet/templates/<name>.html`, show preview, get approval, then continue with the remaining setup questions.

**If user picks C**, load the chosen template HTML and continue.

**If user picks A, D, or E**, no template work needed — proceed to the next setup question.

**Output directory:**
> Where should I save the timesheets?
> (default: ~/Downloads)

**Overtime:**
> Allow overtime (more than configured hours per day)?
> A) No — strict cap at configured hours/day
> B) Yes — allow up to 10h/day when workload is heavy
> C) Yes — custom max (I'll specify)

**Project mapping:**
> Map git scopes to project names? (useful for time tracking tools)
>
> A) No — leave "Projects" column as "No project"
> B) Yes — I'll set up mappings

If yes, ask for mappings per repo:
> For **my-app**, map commit scopes to project names.
> Default project name for this repo?
> Then specific scopes (e.g., `auth -> Auth Module`, `api -> Backend API`)
> Type "done" when finished.

**Team members** (for multi-member timesheets):
> Generate timesheets for:
>
> A) Just me (single member)
> B) Multiple team members (I'll add names + git authors)

If B, collect for each member: display name, git author patterns, repos to scan.

**Language:**
> What language should the timesheet be in?
>
> A) English (en)
> B) Polish (pl)
> C) German (de)
> D) French (fr)
> E) Spanish (es)
> F) Dutch (nl)
> G) Portuguese (pt)
> H) Italian (it)
> I) Other (I'll type the language code)

The language setting affects:
- Title ("Weekly Timesheet" / "Tygodniowa karta czasu pracy" / "Wochenarbeitszeittabelle")
- Column headers ("Time Entries", "Billable", "Projects", "Total")
- Day abbreviations ("Mon" / "Pon" / "Mo")
- Month names in date headers
- Status labels ("Holiday", "PTO", "Sick")
- Report output text

**Time format:**
> How should time be displayed?
>
> A) H:MM — e.g., 5:30, 2:15 (international standard)
> B) Decimal — e.g., 5.5, 2.25 (common in invoicing)
> C) HH:MM:SS — e.g., 05:30:00, 02:15:00 (full precision)
> D) US AM/PM — e.g., 9:00 AM - 5:30 PM (start/end times per task)

If D (AM/PM mode), generate start and end times for each task instead of durations:
- Day starts at configured time (default 9:00 AM)
- Tasks are sequential within a day
- Lunch break inserted automatically (default 12:00 PM - 1:00 PM)
- Example: 9:00 AM - 11:45 AM (2:45), 1:00 PM - 6:15 PM (5:15)

**Date format:**
> How should dates be displayed in headers?
>
> A) D MMM YYYY — 3 Mar 2026 (international)
> B) MMM D, YYYY — Mar 3, 2026 (US)
> C) DD/MM/YYYY — 03/03/2026 (EU)
> D) MM/DD/YYYY — 03/03/2026 (US numeric)
> E) YYYY-MM-DD — 2026-03-03 (ISO)

**Push to time tracker (optional):**
> Push time entries directly to a time tracking tool?
>
> A) No — just generate files
> B) Toggl Track
> C) Clockify
> D) TMetric
> E) Harvest

If B-E, ask for API credentials:
> Enter your {tool} API token:
> (Find it in {tool}'s settings → API → Personal API Token)

**SECURITY: NEVER store API tokens in profile JSON files.** Profiles may be committed to repos or shared. Instead, use environment variables:

```bash
# User sets these in their shell profile (.bashrc, .zshrc, PowerShell profile)
export GIT_TIMESHEET_TOGGL_TOKEN="your-token-here"
export GIT_TIMESHEET_CLOCKIFY_TOKEN="your-token-here"
export GIT_TIMESHEET_TMETRIC_TOKEN="your-token-here"
export GIT_TIMESHEET_HARVEST_TOKEN="your-token-here"
export GIT_TIMESHEET_HARVEST_ACCOUNT_ID="your-account-id"
```

Profile stores only the service name and workspace ID (non-secret):
```json
{
  "settings": {
    "pushTo": {
      "service": "toggl",
      "workspaceId": "123456"
    }
  }
}
```

At runtime, read the token from the environment:
```bash
# Check if token is set
echo $GIT_TIMESHEET_TOGGL_TOKEN | head -c4
```

If the env var is not set, ask the user to set it and provide instructions:
> Your Toggl API token is not configured.
> 
> 1. Go to Toggl → Profile Settings → API Token
> 2. Copy the token
> 3. Add to your shell profile:
>    `export GIT_TIMESHEET_TOGGL_TOKEN="your-token"`
> 4. Restart your terminal and try again

**Template:** Already handled in the **Output format** question above. Skip — do not ask separately.

**Save profile:**
> Save these settings as a profile for next time?
>
> A) Yes — name it: ___
> B) No — one-time run

### Step 1: Resolve Holidays

Based on the selected country, determine public holidays in the date range.

Calculate holidays using Python. The script includes the **computus algorithm** for Easter-dependent holidays and **nth-weekday-of-month** logic for relative holidays (e.g., Thanksgiving = 4th Thursday of November).

**Note for Python availability:** On Windows, try `py -c` first, then `python3 -c`, then `python -c`. On macOS/Linux, use `python3 -c`.

```bash
python3 -c "
import datetime, json, sys

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today().year
COUNTRY = sys.argv[2] if len(sys.argv) > 2 else 'US'

# --- Easter calculation (Anonymous Gregorian algorithm / computus) ---
def easter(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)

# --- Nth weekday of month (0=Mon, 6=Sun) ---
def nth_weekday(year, month, weekday, n):
    first = datetime.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + datetime.timedelta(days=offset + 7 * (n - 1))

# --- Last weekday of month ---
def last_weekday(year, month, weekday):
    if month == 12:
        last_day = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    offset = (last_day.weekday() - weekday) % 7
    return last_day - datetime.timedelta(days=offset)

E = easter(YEAR)

HOLIDAYS = {
    'US': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('MLK Day', nth_weekday(YEAR, 1, 0, 3)),
        ('Presidents\\' Day', nth_weekday(YEAR, 2, 0, 3)),
        ('Memorial Day', last_weekday(YEAR, 5, 0)),
        ('Independence Day', datetime.date(YEAR, 7, 4)),
        ('Labor Day', nth_weekday(YEAR, 9, 0, 1)),
        ('Columbus Day', nth_weekday(YEAR, 10, 0, 2)),
        ('Veterans Day', datetime.date(YEAR, 11, 11)),
        ('Thanksgiving', nth_weekday(YEAR, 11, 3, 4)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
    ],
    'PL': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('Epiphany', datetime.date(YEAR, 1, 6)),
        ('Easter Monday', E + datetime.timedelta(days=1)),
        ('Labour Day', datetime.date(YEAR, 5, 1)),
        ('Constitution Day', datetime.date(YEAR, 5, 3)),
        ('Corpus Christi', E + datetime.timedelta(days=60)),
        ('Assumption', datetime.date(YEAR, 8, 15)),
        ('All Saints\\' Day', datetime.date(YEAR, 11, 1)),
        ('Independence Day', datetime.date(YEAR, 11, 11)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
        ('Second Day of Christmas', datetime.date(YEAR, 12, 26)),
    ],
    'GB': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('Good Friday', E - datetime.timedelta(days=2)),
        ('Easter Monday', E + datetime.timedelta(days=1)),
        ('Early May Bank Holiday', nth_weekday(YEAR, 5, 0, 1)),
        ('Spring Bank Holiday', last_weekday(YEAR, 5, 0)),
        ('Summer Bank Holiday', last_weekday(YEAR, 8, 0)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
        ('Boxing Day', datetime.date(YEAR, 12, 26)),
    ],
    'DE': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('Good Friday', E - datetime.timedelta(days=2)),
        ('Easter Monday', E + datetime.timedelta(days=1)),
        ('Labour Day', datetime.date(YEAR, 5, 1)),
        ('Ascension Day', E + datetime.timedelta(days=39)),
        ('Whit Monday', E + datetime.timedelta(days=50)),
        ('German Unity Day', datetime.date(YEAR, 10, 3)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
        ('Second Christmas Day', datetime.date(YEAR, 12, 26)),
    ],
    'AU': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('Australia Day', datetime.date(YEAR, 1, 26)),
        ('Good Friday', E - datetime.timedelta(days=2)),
        ('Easter Saturday', E - datetime.timedelta(days=1)),
        ('Easter Monday', E + datetime.timedelta(days=1)),
        ('Anzac Day', datetime.date(YEAR, 4, 25)),
        ('Queen\\'s Birthday', nth_weekday(YEAR, 6, 0, 2)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
        ('Boxing Day', datetime.date(YEAR, 12, 26)),
    ],
    'NZ': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('Day after New Year', datetime.date(YEAR, 1, 2)),
        ('Waitangi Day', datetime.date(YEAR, 2, 6)),
        ('Good Friday', E - datetime.timedelta(days=2)),
        ('Easter Monday', E + datetime.timedelta(days=1)),
        ('Anzac Day', datetime.date(YEAR, 4, 25)),
        ('Queen\\'s Birthday', nth_weekday(YEAR, 6, 0, 1)),
        ('Matariki', datetime.date(YEAR, 6, 20)),  # approximate
        ('Labour Day', nth_weekday(YEAR, 10, 0, 4)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
        ('Boxing Day', datetime.date(YEAR, 12, 26)),
    ],
    'CA': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('Good Friday', E - datetime.timedelta(days=2)),
        ('Victoria Day', last_weekday(YEAR, 5, 0) - datetime.timedelta(days=7) if last_weekday(YEAR, 5, 0).day > 24 else last_weekday(YEAR, 5, 0)),
        ('Canada Day', datetime.date(YEAR, 7, 1)),
        ('Labour Day', nth_weekday(YEAR, 9, 0, 1)),
        ('Thanksgiving', nth_weekday(YEAR, 10, 0, 2)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
        ('Boxing Day', datetime.date(YEAR, 12, 26)),
    ],
    'FR': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('Easter Monday', E + datetime.timedelta(days=1)),
        ('Labour Day', datetime.date(YEAR, 5, 1)),
        ('Victory in Europe Day', datetime.date(YEAR, 5, 8)),
        ('Ascension Day', E + datetime.timedelta(days=39)),
        ('Whit Monday', E + datetime.timedelta(days=50)),
        ('Bastille Day', datetime.date(YEAR, 7, 14)),
        ('Assumption', datetime.date(YEAR, 8, 15)),
        ('All Saints\\' Day', datetime.date(YEAR, 11, 1)),
        ('Armistice Day', datetime.date(YEAR, 11, 11)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
    ],
    'NL': [
        ('New Year\\'s Day', datetime.date(YEAR, 1, 1)),
        ('Good Friday', E - datetime.timedelta(days=2)),
        ('Easter Monday', E + datetime.timedelta(days=1)),
        ('King\\'s Day', datetime.date(YEAR, 4, 27)),
        ('Liberation Day', datetime.date(YEAR, 5, 5)),
        ('Ascension Day', E + datetime.timedelta(days=39)),
        ('Whit Monday', E + datetime.timedelta(days=50)),
        ('Christmas Day', datetime.date(YEAR, 12, 25)),
        ('Second Christmas Day', datetime.date(YEAR, 12, 26)),
    ],
}

if COUNTRY in HOLIDAYS:
    result = [{'name': n, 'date': d.isoformat()} for n, d in HOLIDAYS[COUNTRY]]
    print(json.dumps(result, indent=2))
else:
    print(f'Unknown country: {COUNTRY}', file=sys.stderr)
    sys.exit(1)
"  <YEAR> <COUNTRY_CODE>
```

Example: `python3 holidays.py 2026 US` outputs all 10 US federal holidays with correct dates.

Combine public holidays with user-specified PTO/sick days into a unified "days off" list. Each entry has:
- `date` (YYYY-MM-DD)
- `reason` (e.g., "New Year's Day", "PTO", "Sick")
- `type` ("holiday" | "pto" | "sick")

### Step 2: Parse Date Range

**Range presets and custom ranges resolve to ISO dates first. Then ISO normalization rules below apply to any free-text input.**

**Built-in range presets:**

| Name | Resolves to | Offset support |
|---|---|---|
| `first-half` | 1st → 15th of current month | `:2026-03`, `:march`, `:mar` |
| `second-half` | 16th → last day of current month | same offsets |
| `full-month` | 1st → last day of current month | same offsets |
| `last-month` | 1st → last day of previous month | none |
| `this-week` | Mon → Sun of current ISO week | none |
| `last-week` | Mon → Sun of previous ISO week | none |

Compute "last day of month" with:

```python
last_day = (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day if month < 12 \
           else (datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)).day
```

**Custom ranges** come from `profile.customRanges`:

| Type | Schema | Resolution |
|---|---|---|
| `monthDays` | `{ "monthDays": [start, end] }` | Days within current month; `"last"` = last day of month |
| `monthRange` | `{ "monthRange": [startMonth, endMonth] }` | First-of-startMonth → last-of-endMonth in current year |
| `weekOffset` | `{ "weekOffset": <n> }` | ISO week relative to current (0 = this week, -1 = last week) |

**ISO normalization rules** (apply to free-text input, not to presets):

Always normalize user date input to ISO `YYYY-MM-DD` before any git operations. Date input formats vary by region — never assume US `MM/DD/YYYY`.

Common formats to handle:

| User input | ISO normalized |
|---|---|
| `1 Apr to 15 Apr` | `<year>-04-01` to `<year>-04-15` |
| `1.04 to 15.04` | `<year>-04-01` to `<year>-04-15` (EU: `D.MM`) |
| `01.04.2026 - 15.04.2026` | `2026-04-01` to `2026-04-15` |
| `01/04/2026 - 15/04/2026` | EU: `2026-04-01` to `2026-04-15` |
| `4/1/2026 - 4/15/2026` | US: `2026-04-01` to `2026-04-15` |
| `2026-04-01 to 2026-04-15` | already ISO |

**Disambiguation rules:**

- If the user's profile `country` is anything other than `US` or `CA`, default ambiguous numeric formats to **EU `D.MM` / `DD.MM.YYYY`**.
- For ambiguous inputs like `1/4/2026` (could be Jan 4 US or 1 Apr EU), confirm explicitly: *"I'm reading this as 1 April 2026 — correct?"*
- Numeric formats with no year (`1.04`, `15.04`) default to the **current year**.
- Both bounds are **inclusive**: `1 Apr to 15 Apr` includes commits made on April 1 AND April 15.

**Confirmation step (MANDATORY):**

Before running any git commands, show the user the resolved range so date misinterpretation is caught before it costs a manual correction:

> Searching commits from **2026-04-01 (Wed)** to **2026-04-15 (Wed)** — both dates inclusive.
> That's 11 working days (Mon-Fri), excluding weekends and PTO/holidays.
>
> A) Looks correct, continue
> B) Wrong dates — let me re-enter

Determine which ISO weeks (Mon-Sun) fall within the range. Each week becomes one timesheet. For multi-member profiles, generate one set of timesheets per member.

### Step 3: Gather Git History

**Use ISO dates only — never raw user input.** Use explicit `00:00:00` / `23:59:59` timestamps to remove any timezone-cutoff ambiguity that would silently drop commits at the boundaries.

For each member and each of their repositories, run:

```bash
git -C "<repo-path>" log \
  --after="<start-iso> 00:00:00" \
  --before="<end-iso> 23:59:59" \
  --author="<pattern1>\|<pattern2>" \
  --format="%ad | %s" --date=short --shortstat | paste - - -
```

This gives commit date, message, and lines changed in one line.

**Commit count summary (MANDATORY):**

After gathering commits from all repos, show this BEFORE generating timesheets:

> Found **23 commits** across **3 repos** for **Jane Doe** (2026-04-01 → 2026-04-15):
>
> | Repo | Commits | Most recent |
> |---|---|---|
> | my-app | **12** | 2026-04-14 |
> | shared-lib | **8** | 2026-04-15 |
> | other-repo | **3** | 2026-04-09 |
>
> Looks right?
>
> A) Yes, continue
> B) Add more author patterns / repos
> C) Adjust date range
> D) I expected commits in a repo that aren't shown — investigate

**If D**, list every git author found in the suspect repo for the date range so the user can spot mismatches (e.g., commits made under a different email):

```bash
git -C "<repo-path>" log \
  --after="<start-iso> 00:00:00" \
  --before="<end-iso> 23:59:59" \
  --format="%aN <%ae>" | sort -u
```

This catches the most common "missing commit" failures: wrong author pattern, missing repo, date range parsed incorrectly, or commits made under a secondary email.

### Step 4: Clean Up Commit Messages

Apply these transformations to make task descriptions cleaner:

1. **Strip PR numbers:** `(#2505)` → removed
2. **Strip trailing refs:** `Refs: TICKET-1234` → move ticket ID to description
3. **Merge ticket + description:** `fix(order): clear payments (#2505) Refs: PROJ-8450` → `fix(order): Clear payments (PROJ-8450)`
4. **Truncate long messages:** Max 80 characters, add `...` if truncated
5. **Capitalize first word after colon:** `fix(order): clear` → `fix(order): Clear`
6. **Strip trailing GitHub truncation ellipsis:** `prevent freeze after consecutive Save &…` → `prevent freeze after consecutive Save &`

Regex patterns:

```
# Remove PR numbers
s/\s*\(#\d+\)//g

# Extract Refs ticket
s/\s*Refs:\s*([A-Z]+-\d+)// → append ($1) to description if not already present

# Truncate
if len > 80: description[:77] + "..."
```

### Step 5: Group Commits by Week and Day

- Group all commits (across repos) by ISO week
- Within each week, group by day of week (work days only)
- Weekend commits → attribute to nearest weekday
- Holiday/PTO/sick day commits → attribute to nearest working day
- Merge related commits (same scope + same day) into single entries

### Step 6: Allocate Time Based on Complexity

**Rules:**
- Every **working day** (not holiday/PTO/sick) MUST total exactly the configured hours
- Holidays show **"Holiday: {name}"** with 0 hours
- PTO days show **"PTO"** with 0 hours
- Sick days show **"Sick"** with 0 hours
- Weekends are always **"-"** (dash)
- Time allocation uses the configured increment (default **15 minutes**)

**Valid time values at 15-min increments:**
`0:15, 0:30, 0:45, 1:00, 1:15, 1:30, 1:45, 2:00, 2:15, 2:30, 2:45, 3:00, 3:15, 3:30, 3:45, 4:00, 4:15, 4:30, 4:45, 5:00, 5:15, 5:30, 5:45, 6:00, 6:15, 6:30, 6:45, 7:00, 7:15, 7:30, 7:45, 8:00`

**Complexity scoring:**
- Count insertions + deletions per commit
- Count files changed per commit
- Score = `(lines_changed * 1) + (files_changed * 10)`
- Higher score = more hours allocated
- Minimum score floor: even a 1-line fix gets score 20 (investigation + testing)

**Distribution within a day:**
- If 1 task: give it the full day
- If 2 tasks: split proportionally by score. Use varied splits like:
  - 5:15+2:45, 5:45+2:15, 6:00+2:00, 4:30+3:30, 6:30+1:30
  - **NEVER** split evenly (4:00+4:00) — always vary!
- If 3+ tasks: distribute proportionally, minimum 1:00 per task
- If overtime allowed and day is overloaded: allow up to maxHoursPerDay

**Spreading work across empty days:**
- If a day has no commits but adjacent days are overloaded, move work to the empty day
- The goal: every working day = configured hours (unless overtime)
- Priority: fill empty days first, then redistribute from overloaded days

### Step 7: Map Projects

If project mapping is configured:

1. For each task entry, determine the source repo
2. Extract the scope from the commit message: `type(scope): ...` → scope
3. Look up in projectMapping: `repo → scopes → scope` or fall back to `repo → default`
4. If no mapping found, use "No project"

The "Projects" column in the output shows the mapped project name.

### Step 8: Generate Output

**Playwright availability check:** Before attempting PDF generation, verify that Playwright MCP tools are available. If `mcp__playwright__browser_navigate` is not in the available tools list, automatically fall back to CSV-only output and inform the user:

> Playwright MCP is not configured — generating CSV output only.
> To enable PDF output, install the Playwright plugin: `/plugin install playwright`

#### PDF Format

Create one HTML file per week per member using the configured template (or the default below).

Default HTML template:

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: A4 landscape; margin: 20mm; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; margin: 0; padding: 40px; }
  h1 { font-size: 28px; font-weight: 700; margin: 0 0 24px 0; }
  .header-row { display: flex; margin-bottom: 6px; font-size: 15px; }
  .header-label { width: 120px; color: #666; }
  .header-value { font-weight: 600; }
  table { border-collapse: collapse; width: 100%; margin-top: 24px; font-size: 13px; }
  th, td { border: 1px solid #ddd; padding: 8px 10px; text-align: center; }
  th { background: #f8f9fa; font-weight: 600; }
  td:first-child { text-align: left; max-width: 280px; }
  .day-header { font-size: 12px; line-height: 1.4; }
  .day-header .dow { font-weight: 600; }
  .totals-row td { font-weight: 700; background: #f8f9fa; }
  .total-col { font-weight: 700; }
  .holiday { color: #e74c3c; font-style: italic; font-size: 11px; }
  .pto { color: #f39c12; font-style: italic; font-size: 11px; }
  .sick { color: #9b59b6; font-style: italic; font-size: 11px; }
</style>
</head>
<body>
<h1>Weekly Timesheet</h1>
<!-- Header rows: Member, Period, Total Time -->
<!-- Table: Time Entries | Billable | Projects | Mon-Sun headers | Total -->
<!-- Day headers show holiday/PTO/sick labels: -->
<!-- <div class="holiday">New Year's Day</div> -->
<!-- <div class="pto">PTO</div> -->
<!-- <div class="sick">Sick</div> -->
<!-- Totals row: hours for working days, "Holiday"/"PTO"/"Sick"/"-" for off days -->
</body>
</html>
```

Convert HTML to PDF via Playwright:

```javascript
// Serve HTML files with a local HTTP server, then:
await page.goto('http://localhost:8772/filename.html');
await page.pdf({
  format: 'A4',
  landscape: true,
  printBackground: true,
  margin: { top: '20mm', bottom: '20mm', left: '20mm', right: '20mm' },
  path: 'output/filename.pdf'
});
```

**HTTP server cross-platform:**
- Windows: `py -m http.server 8772 --directory <dir>`
- macOS/Linux: `python3 -m http.server 8772 --directory <dir>`

Process all files in a single `browser_run_code` call for efficiency.

#### CSV Format

```csv
User,Time Entry,Task,Project,Billable,Tags,Work Type,Link,YYYY-MM-DD,YYYY-MM-DD,...,Total
Jane Doe,task description,,Project Name,Yes,,,,H:MM,-,...,H:MM
```

### ⚠️ Billable column — CRITICAL

**Every entry MUST be `Billable: Yes` by default. Non-negotiable.**

The ONLY exception is when the loaded profile has `settings.billable === "no"`. Default value is `"yes"`.

**DO NOT MIRROR sample data from any of these sources:**
- `examples/sample-timesheet.pdf` (the bundled example) — its rendered "No" values are STALE; only its layout is current
- Any previously generated PDF in `~/Downloads/` (older runs may have wrong Billable values)
- Any company/imported template the user provided (those describe LAYOUT, not data)
- The HTML template's example rows (samples for structure only)

When generating output, the Billable column value comes from **the profile setting (or the default `"yes"`)** — never from a reference PDF, never from prior output, never from a template's sample row.

Only rows with `Billable: Yes` count toward the invoice summary in Step 10.5.

### General rule for ALL data values

When generating timesheets, **the only sources of truth are**:
1. The user's profile settings (loaded from `~/.claude/skills/timesheet/profiles/<name>.json`)
2. Live git log output for the requested date range
3. Computed time allocations (Step 6)
4. Project mappings (Step 7)
5. The user's interactive answers in this session

Reference materials (sample PDF, sample CSV in this skill, imported company templates, prior generated files) provide **STRUCTURE ONLY** — the columns to include, the layout, the styling. Do not copy any row's values, names, projects, dates, hours, billable status, or other data from them.

- One CSV per week per member
- Column headers use ISO dates for each day
- Holiday/PTO/sick columns show the reason instead of "-"
- Projects column shows mapped project name

### Step 9: Cleanup

- Delete all generated `.html` files (if PDF)
- Delete any Python helper scripts
- Kill the HTTP server (if started)
- Delete any Playwright snapshot artifacts

### Step 10: Report

List the generated files with a detailed summary:

```
Generated 4 timesheets for Jane Doe:

  Timesheet_Jane_Doe_Weekly_20260216_20260222.pdf
   6 entries | 40:00 total | 5 work days

  Timesheet_Jane_Doe_Weekly_20260223_20260301.pdf
   5 entries | 32:00 total | 4 work days
   Wed 25 Feb — PTO

  Timesheet_Jane_Doe_Weekly_20260302_20260308.pdf
   7 entries | 40:00 total | 5 work days

  Timesheet_Jane_Doe_Weekly_20260309_20260315.pdf
   8 entries | 40:00 total | 5 work days

Days off in this period:
   Wed 25 Feb — PTO
   No public holidays in this range

Profile used: my-profile
```

If `--save-profile` was requested or user opted to save, confirm:
```
Profile saved: ~/.claude/skills/timesheet/profiles/my-profile.json
```

### Step 10.5: Invoice Summary (optional)

After the file listing, ask whether the user wants an invoice total for the generated period:

> Do you want an invoice summary (total hours × hourly rate)?
>
> A) Yes
> B) No

**If A:**

1. Check the loaded profile for `invoicing.hourlyRate` and `invoicing.currency`. If present, offer it:

   > Use saved rate **85.00 USD/hr**?
   >
   > A) Yes, use it
   > B) No, enter a different rate

2. Otherwise (or if the user picked B above), ask:

   > What's your hourly rate?
   > Enter as `<amount> <currency-code>`, e.g., `85 USD`, `350 PLN`, `70 EUR`

3. Parse rate and currency. Sum **total hours across billable entries only** (rows where `Billable: Yes` — see Step 8). Convert H:MM to decimal for the math. Compute `totalPayment = totalHours_decimal × rate`.

4. Display the summary:

   > **Invoice Summary** (2026-04-01 → 2026-04-15):
   >
   > | Metric | Value |
   > |---|---|
   > | Weeks included | 3 |
   > | Total hours | 120:00 (120.00 h) |
   > | Hourly rate | 85.00 USD |
   > | **Total payment** | **10,200.00 USD** |

   Round total payment to 2 decimal places. Format numbers with the user's locale-appropriate thousands separator when possible.

5. If the rate was **not** loaded from the profile, offer to save it:

   > Save this rate (**85.00 USD/hr**) to your profile for next time?
   >
   > A) Yes
   > B) No — one-time use only

   If A: add/update the `invoicing` object in the profile JSON and rewrite the file.

**If B (no invoice summary):** skip this step entirely — do not prompt further.

### Step 11: Push to Time Tracker (optional)

If `pushTo` is configured in the profile, push the generated time entries directly to the API.

**Before pushing, always confirm:**
> Ready to push {N} time entries to {service} for {date range}.
>
> A) Push all entries
> B) Let me review first (shows entries in a table)
> C) Cancel — just keep the files

#### Toggl Track API

- **Base URL:** `https://api.track.toggl.com/api/v9`
- **Auth:** Basic auth with `{apiToken}:api_token`
- **Create time entry:** `POST /workspaces/{workspaceId}/time_entries`

```bash
curl -s -u "{apiToken}:api_token" \
  -H "Content-Type: application/json" \
  -X POST "https://api.track.toggl.com/api/v9/workspaces/{workspaceId}/time_entries" \
  -d '{
    "description": "feat(auth): Implement OAuth2 login flow",
    "start": "2026-03-03T09:00:00+00:00",
    "duration": 20700,
    "workspace_id": {workspaceId},
    "project_id": null,
    "created_with": "git-timesheet"
  }'
```

Fields:
- `description` — task description from commit message
- `start` — ISO 8601 datetime (date + configured start time)
- `duration` — seconds (e.g., 5:45 = 20700s)
- `project_id` — look up by name from project mapping, or null
- `created_with` — always "git-timesheet"

**Workspace discovery:** `GET /me?with_related_data=true` → `workspaces[].id`
**Project lookup:** `GET /workspaces/{wid}/projects` → match by name

#### Clockify API

- **Base URL:** `https://api.clockify.me/api/v1`
- **Auth:** Header `X-Api-Key: {apiToken}`
- **Create time entry:** `POST /workspaces/{workspaceId}/time-entries`

```bash
curl -s -H "X-Api-Key: {apiToken}" \
  -H "Content-Type: application/json" \
  -X POST "https://api.clockify.me/api/v1/workspaces/{workspaceId}/time-entries" \
  -d '{
    "start": "2026-03-03T09:00:00Z",
    "end": "2026-03-03T14:45:00Z",
    "description": "feat(auth): Implement OAuth2 login flow",
    "projectId": null
  }'
```

Fields:
- `start` / `end` — ISO 8601 datetimes
- `description` — task description
- `projectId` — look up by name, or null

**Workspace discovery:** `GET /user` → `activeWorkspace`
**Project lookup:** `GET /workspaces/{wid}/projects` → match by name

#### TMetric API

- **Base URL:** `https://app.tmetric.com/api`
- **Auth:** Bearer token or API key
- **Create time entry:** `POST /accounts/{accountId}/timeentries`

```bash
curl -s -H "Authorization: Bearer {apiToken}" \
  -H "Content-Type: application/json" \
  -X POST "https://app.tmetric.com/api/accounts/{accountId}/timeentries" \
  -d '{
    "startTime": "2026-03-03T09:00:00",
    "endTime": "2026-03-03T14:45:00",
    "note": "feat(auth): Implement OAuth2 login flow",
    "projectId": null
  }'
```

Fields:
- `startTime` / `endTime` — datetime strings
- `note` — task description
- `projectId` — look up by name, or null

**Account discovery:** `GET /accounts` → `[].id`
**Project lookup:** `GET /accounts/{id}/timeentries/projects` → match by name

#### Harvest API

- **Base URL:** `https://api.harvestapp.com/v2`
- **Auth:** Bearer token + `Harvest-Account-Id` header
- **Create time entry:** `POST /time_entries`

```bash
curl -s -H "Authorization: Bearer {apiToken}" \
  -H "Harvest-Account-Id: {accountId}" \
  -H "Content-Type: application/json" \
  -X POST "https://api.harvestapp.com/v2/time_entries" \
  -d '{
    "project_id": 12345,
    "task_id": 67890,
    "spent_date": "2026-03-03",
    "hours": 5.75,
    "notes": "feat(auth): Implement OAuth2 login flow"
  }'
```

Fields:
- `spent_date` — YYYY-MM-DD
- `hours` — decimal hours (e.g., 5.75 for 5:45)
- `notes` — task description
- `project_id` / `task_id` — required, look up from Harvest projects

**Account discovery:** `GET /users/me` → accounts
**Project lookup:** `GET /projects` → match by name
**Task lookup:** `GET /projects/{id}/task_assignments` → get default task

#### Push error handling

- **401 Unauthorized:** API token is invalid or expired. Ask user to update.
- **Rate limiting (429):** Back off and retry with increasing delays (1s, 2s, 4s).
- **Duplicate detection:** Before pushing, check if entries already exist for the same date range. If yes, warn:
  > Found {N} existing entries in {service} for this date range.
  >
  > A) Skip duplicates — only push new entries
  > B) Replace all — delete existing and push fresh
  > C) Cancel push
- **Partial failure:** If some entries fail, report which ones succeeded and which failed with error details.

#### Post-push report

```
Pushed 28 time entries to Toggl Track:

  Week of 2-8 Mar: 7 entries pushed
  Week of 9-15 Mar: 8 entries pushed
  Week of 16-22 Mar: 6 entries pushed
  Week of 23-29 Mar: 7 entries pushed

  0 skipped (duplicates)
  0 failed

Toggl workspace: My Company (ID: 123456)
```

## Time Format Details

### H:MM (default)
Standard duration format. Used in table cells.
- `5:30` = 5 hours 30 minutes
- `0:45` = 45 minutes

### Decimal
Hours as decimal numbers. Common in invoicing/billing.
- `5.5` = 5 hours 30 minutes
- `0.75` = 45 minutes
- Round to nearest increment (0.25 for 15-min, 0.5 for 30-min)

### HH:MM:SS
Full precision format.
- `05:30:00` = 5 hours 30 minutes
- `00:45:00` = 45 minutes

### US AM/PM (start/end times)
Instead of duration, show when each task started and ended.
Adds two extra columns: "Start" and "End" (replaces the per-day hours).

Layout changes:
- Day columns show `9:00 AM - 2:45 PM` instead of `5:45`
- A separate "Duration" column shows the total
- Lunch break (configurable, default 12:00 PM - 1:00 PM) is excluded from work time
- Day starts at configurable time (default 9:00 AM)

Profile fields for AM/PM mode:
```json
{
  "settings": {
    "timeFormat": "AM/PM",
    "dayStartTime": "09:00",
    "lunchBreak": { "start": "12:00", "end": "13:00" }
  }
}
```

## Language / i18n

All user-facing text in the generated timesheet is translated based on the `language` setting.

### Translation table

| Key | en | pl | de | fr | es | nl |
|-----|----|----|----|----|----|----|
| title | Weekly Timesheet | Tygodniowa karta czasu pracy | Wochenarbeitszeittabelle | Feuille de temps hebdomadaire | Hoja de horas semanal | Wekelijkse urenstaat |
| member | Member | Pracownik | Mitarbeiter | Membre | Miembro | Medewerker |
| period | Period | Okres | Zeitraum | Période | Período | Periode |
| totalTime | Total Time | Czas całkowity | Gesamtzeit | Temps total | Tiempo total | Totale tijd |
| timeEntries | Time Entries | Wpisy czasu | Zeiteinträge | Entrées de temps | Entradas de tiempo | Tijdregistraties |
| billable | Billable | Rozliczane | Abrechenbar | Facturable | Facturable | Facturabel |
| projects | Projects | Projekty | Projekte | Projets | Proyectos | Projecten |
| total | Total | Razem | Gesamt | Total | Total | Totaal |
| holiday | Holiday | Święto | Feiertag | Jour férié | Festivo | Feestdag |
| pto | PTO | Urlop | Urlaub | Congé | Vacaciones | Verlof |
| sick | Sick | Chorobowe | Krank | Maladie | Enfermedad | Ziek |
| noProject | No project | Brak projektu | Kein Projekt | Aucun projet | Sin proyecto | Geen project |

### Day abbreviations

| Day | en | pl | de | fr | es | nl |
|-----|----|----|----|----|----|----|
| Monday | Mon | Pon | Mo | Lun | Lun | Ma |
| Tuesday | Tue | Wt | Di | Mar | Mar | Di |
| Wednesday | Wed | Śr | Mi | Mer | Mié | Wo |
| Thursday | Thu | Czw | Do | Jeu | Jue | Do |
| Friday | Fri | Pt | Fr | Ven | Vie | Vr |
| Saturday | Sat | Sob | Sa | Sam | Sáb | Za |
| Sunday | Sun | Ndz | So | Dim | Dom | Zo |

### Month names

| Month | en | pl | de | fr | es | nl |
|-------|----|----|----|----|----|----|
| 1 | Jan | Sty | Jan | Jan | Ene | Jan |
| 2 | Feb | Lut | Feb | Fév | Feb | Feb |
| 3 | Mar | Mar | Mär | Mar | Mar | Mrt |
| 4 | Apr | Kwi | Apr | Avr | Abr | Apr |
| 5 | May | Maj | Mai | Mai | May | Mei |
| 6 | Jun | Cze | Jun | Jun | Jun | Jun |
| 7 | Jul | Lip | Jul | Jul | Jul | Jul |
| 8 | Aug | Sie | Aug | Aoû | Ago | Aug |
| 9 | Sep | Wrz | Sep | Sep | Sep | Sep |
| 10 | Oct | Paź | Okt | Oct | Oct | Okt |
| 11 | Nov | Lis | Nov | Nov | Nov | Nov |
| 12 | Dec | Gru | Dez | Déc | Dic | Dec |

### How to apply translations

When generating HTML or CSV output:
1. Look up the `language` from the profile/settings
2. Replace all hardcoded English labels with the translated version from the tables above
3. Use translated day abbreviations in the table column headers
4. Use translated month abbreviations in date displays
5. Holiday names should remain in the country's native language (e.g., Polish holidays stay in Polish regardless of the `language` setting, since they are proper nouns)

For languages not in the table (e.g., `pt`, `it`, `ja`), Claude should translate the labels dynamically using its language knowledge, following the same pattern.

## Edge Cases

- **No commits in a week:** Ask the user what they worked on (unless full PTO week)
- **All commits on one day:** Spread across the week realistically
- **Very small fix (1-2 lines):** Minimum 1:00 (investigation + testing takes time)
- **Huge commit (docs, generated code):** Cap at full day; docs/config get less time than feature code
- **Holiday week:** Reduce total hours, redistribute across remaining work days
- **Full PTO week:** Show all days as PTO, 0:00 total, no entries needed
- **Sick day with commits:** Still mark as sick (they shouldn't have been working!)
- **Overtime day:** If allowed, can exceed normal hours; show actual total in red
- **Multiple members same week:** Generate separate timesheets, one PDF/CSV per member
- **No profile found:** Run full interactive setup, offer to save at end
- **Repo not found on disk:** Warn and skip, continue with other repos
