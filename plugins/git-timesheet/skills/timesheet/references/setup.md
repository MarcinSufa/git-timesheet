# Setup questions

All questions are plain markdown in chat (never `AskUserQuestion`, Plan mode or
any selection widget). Skip a question only when a loaded profile or the
command-line arguments already answer it.

## Question 1 — Profile selection

Skip if `--profile` was given or exactly one profile exists. Build the list from
the `profiles` that `datadir.py` printed:

> Found saved profiles:
>
> A) **my-profile** — Jane Doe (my-app, shared-lib) [US, 8h/day, PDF]
> B) **team-acme** — 3 members (my-app, shared-lib) [US, 8h/day, PDF]
> C) Create new profile
> D) One-time run (no profile)

## Question 3 — Days off (always ask)

> Any days off in this period? (PTO, sick days, personal leave)
>
> A) No days off
> B) Yes — I'll list them (e.g., "3 Mar PTO, 7 Mar sick")
> C) Yes — full weeks off (e.g., "week of 10 Mar")

Turn the answer into `--day-off` values: `2026-03-03:pto`,
`2026-03-07:sick`, `2026-03-09..2026-03-13:pto`, optionally with a reason
(`2026-03-03:pto:Dentist`). Public holidays come from the country setting and
are not entered here.

## Question 4 — Settings confirmation (profile loaded)

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

On **B**: if the same message says what to change ("change country to US"),
change just that and re-show the summary. Otherwise ask:

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

After every change re-show the summary and ask A/B again. Loop until A.

## First run (no profile): mandatory questions

Ask each one, in this order, and do not infer or default any answer — the user
wants explicit control on the first run.

**Your name:**
> What name should appear on the timesheets?

**Git author patterns:**
> What git author name(s) or email(s) should I search for?
> (comma-separated, e.g., "janedoe, Jane Doe, user@example.com")

Patterns are plain text, matched case-insensitively against author name and
email; any pattern matches.

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

Hours per day must be a multiple of the increment (7.5 h needs 15 or 30 min).

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

J is stored as `"none"`. For K: only the nine calendars above are built in
(national level, no states/provinces; see the `holidays.py` docstring). Store
the code anyway — `holidays.py` then prints a notice and no holidays — and in
Question 3 ask the user for the public holidays in the range; pass them as
`--day-off 2026-05-01:holiday:Labour Day` so they show as holidays.

**Output format + PDF template (one question):**

Show option C once per template in the data dir (`templates` from `datadir.py`):

> What format do you want the timesheets in?
>
> A) PDF — default template (clean weekly grid, tmetric-style)
> B) PDF — match my company's format (I'll provide a sample PDF/PNG/JPG/DOCX)
> C) PDF — use saved template: `<name>`
> D) CSV (importable to tmetric / Toggl / spreadsheets)
> E) Both PDF (default template) and CSV

B → ask *"Drop the file path to your timesheet example (PDF, PNG, JPG, or DOCX):"*
and run the import flow in [templates.md](templates.md), then continue here.

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

If B, per repo:
> For **my-app**, map commit scopes to project names.
> Default project name for this repo?
> Then specific scopes (e.g., `auth -> Auth Module`, `api -> Backend API`)
> Type "done" when finished.

**Team members:**
> Generate timesheets for:
>
> A) Just me (single member)
> B) Multiple team members (I'll add names + git authors)

If B, collect display name, git author patterns and repos for each member.

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

Built-in labels: en, pl, de, fr, es, nl. For any other language see
[i18n.md](i18n.md).

**Time format:**
> How should time be displayed?
>
> A) H:MM — e.g., 5:30, 2:15 (international standard)
> B) Decimal — e.g., 5.5, 2.25 (common in invoicing)
> C) HH:MM:SS — e.g., 05:30:00, 02:15:00 (full precision)
> D) US AM/PM — e.g., 9:00 AM - 5:30 PM (start/end times per task)

For D also ask the day start (default 09:00) and lunch break (default
12:00-13:00, or none); stored as `dayStartTime` and `lunchBreak`.

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

For B-E do **not** ask for the token. Explain the environment variable from
[push.md](push.md) and store only the service name and workspace/account ID.

**Save profile:**
> Save these settings as a profile for next time?
>
> A) Yes — name it: ___
> B) No — one-time run

Write the file to `<data dir>/profiles/<name>.json` following
[profiles.md](profiles.md) and confirm the full path.
