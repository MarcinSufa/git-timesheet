<div align="center">
  <img src="./assets/logo.svg" width="140" alt="git-timesheet" />

  <h1>git-timesheet</h1>

  <p><strong>Stop filling timesheets manually. Let your commits tell the story.</strong></p>

  <p>
    A Claude Code plugin that turns your git history into realistic weekly timesheets.<br />
    Hours are allocated by commit complexity, not split evenly.
  </p>

  <p>
    <img src="https://img.shields.io/badge/version-1.1.0--beta-3b82f6?style=for-the-badge" alt="version" />
    <img src="https://img.shields.io/badge/license-MIT-10b981?style=for-the-badge" alt="license" />
    <img src="https://img.shields.io/badge/Claude%20Code-plugin-8b5cf6?style=for-the-badge" alt="claude code plugin" />
  </p>

  <p>
    <a href="#install">Install</a> ·
    <a href="#quick-start">Quick start</a> ·
    <a href="#how-it-works">How it works</a> ·
    <a href="#custom-pdf-templates">Templates</a> ·
    <a href="#time-tracker-integrations">Integrations</a>
  </p>
</div>

---

## Why

- **Realistic hours** — 8h split proportionally by commit weight, never a flat 4+4
- **Invoice totals** — set your hourly rate once, get `hours × rate` computed
- **Zero data entry** — pick a date range, the rest comes from git
- **Multi-format** — print-ready PDF, importable CSV, or both
- **Push integrations** — Toggl, Clockify, TMetric, Harvest APIs
- **Custom PDF layouts** — import your company's timesheet and match it
- **International** — 9 countries of holidays, 6 built-in languages + dynamic translation

[Sample PDF output](./examples/sample-timesheet.pdf)

---

## Install

Install via the Claude Code plugin marketplace — one command:

```
/plugin marketplace add MarcinSufa/git-timesheet
/plugin install git-timesheet@marcin-sufa-plugins
```

That's it. `/timesheet` is now available in any Claude Code session.

To update later:

```
/plugin marketplace update marcin-sufa-plugins
```

---

## Quick start

```bash
# Interactive — walks you through setup
/timesheet

# Pick a preset period
/timesheet --range first-half           # 1st-15th of current month
/timesheet --range second-half          # 16th-end of current month
/timesheet --range last-month           # 1st-end of previous month

# Custom date range
/timesheet 16 Mar to 15 Apr

# Use a saved profile
/timesheet --profile my-profile

# Import your company's timesheet format
/timesheet --import-template ~/Downloads/company-timesheet.pdf

# Generate and push to time tracker
/timesheet --range first-half --push toggl
```

On first run, the skill asks a handful of questions (git authors, repos, hours/day, country, language, output format). Save the answers as a profile and never set up again.

---

## How it works

```mermaid
flowchart LR
    A[Git history<br/>for date range] --> B[Commit<br/>complexity<br/>scoring]
    B -->|"lines + files × 10"| C[Time<br/>allocation<br/>per day]
    C --> D[PDF<br/>timesheet]
    C --> E[CSV<br/>export]
    C --> F[Invoice<br/>summary]
    D -.-> G[Toggl · Clockify<br/>TMetric · Harvest]
    E -.-> G

    style A fill:#1e293b,stroke:#334155,color:#e2e8f0
    style B fill:#0f172a,stroke:#475569,color:#e2e8f0
    style C fill:#0f172a,stroke:#475569,color:#e2e8f0
    style D fill:#064e3b,stroke:#10b981,color:#d1fae5
    style E fill:#064e3b,stroke:#10b981,color:#d1fae5
    style F fill:#064e3b,stroke:#10b981,color:#d1fae5
    style G fill:#1e293b,stroke:#475569,color:#94a3b8
```

**Allocation example** — a day with two commits:

| Commit | Lines | Files | Score | Time |
|---|---|---|---|---|
| `feat(auth): Add OAuth2 flow` | 150 | 8 | 230 | **7:00** |
| `fix(ui): Button alignment` | 3 | 1 | 20 (floor) | **1:00** |

Result: **7:00 + 1:00 = 8:00** — not 4:00 + 4:00.

Formula: `score = lines_changed + (files_changed × 10)`, minimum 20 (every fix takes investigation + testing). On a day with several entries each gets at least 1:00 and the rest is shared by score, with a little seeded variation so weeks don't look machine-made — the same input always gives the same timesheet. Full rules: [allocation.md](plugins/git-timesheet/skills/timesheet/references/allocation.md).

---

## Features

### Generation

- Weekly timesheets (Mon-Sun) per member, per week in range
- Time allocated proportionally by commit complexity
- Default 8h/day, configurable (8h, 7.5h, 7h, 6h, custom)
- 15-min, 30-min, or 1-hour increments
- Optional overtime cap

### Invoicing

- Post-generation invoice summary
- `hours × hourlyRate` with currency
- Saves your rate to profile for reuse
- Only `Billable: Yes` rows count toward the total

### Holidays & days off

- 9 countries of public holidays built-in:

  `US` · `GB` · `DE` · `PL` · `AU` · `NZ` · `CA` · `FR` · `NL`

- National holidays incl. observed/substitute days (e.g. US Juneteenth, PL Christmas Eve from 2025, NZ Matariki from the official 2022-2030 table, King's Birthday); names in the local language for PL/DE/FR/NL. State/provincial holidays are not included.
- Any other country: add its holidays by hand for the run
- Mark PTO and sick days per run — the remaining work days still get the full hours

### Date presets

- `first-half`, `second-half`, `full-month`, `last-month`, `this-week`, `last-week`
- Offsets: `--range first-half:2026-03` or `--range second-half:march`
- Custom presets saved in profile (e.g., `biweekly-1`, `fiscal-q1`)

### Multi-member

- Single profile can hold a whole team
- Separate git author patterns per member
- One timesheet per member per week

### Project mapping

- Map git `scope(...)` to real project names
- `feat(auth): ...` → "My App — Auth"
- Useful when pushing to Toggl/TMetric where project names matter

---

## Custom PDF templates

Your company has a specific timesheet format? Give the plugin a sample file and it matches it:

```
/timesheet --import-template ~/Downloads/our-timesheet.pdf
```

The plugin analyzes the layout (columns, colors, fonts, logo placement, headers) and generates a matching HTML template. Supports **PDF, PNG, JPG, DOCX** inputs.

Templates are saved in the plugin's data directory (see [Where your data lives](#where-your-data-lives)) and reusable across runs. A template is HTML with placeholders such as `{{title}}` and `{{table}}` — see [templates.md](plugins/git-timesheet/skills/timesheet/references/templates.md).

Refine an existing template via natural language:

```
/timesheet --edit-template company-x
# "make the header bigger"
# "switch to A4 portrait"
# "add the logo at top-right"
```

---

## Profiles

Save your setup once, reuse forever:

```json
{
  "name": "my-profile",
  "members": [
    {
      "displayName": "Jane Doe",
      "gitAuthors": ["janedoe", "Jane"],
      "repos": [
        { "path": "/home/jane/projects/my-app", "label": "my-app" }
      ]
    }
  ],
  "settings": {
    "hoursPerDay": 8,
    "timeIncrement": 15,
    "country": "US",
    "outputFormat": "pdf",
    "timeFormat": "H:MM",
    "dateFormat": "MMM D, YYYY",
    "language": "en",
    "billable": "yes",
    "template": "default",
    "pushTo": { "service": "toggl", "workspaceId": "123456" }
  },
  "customRanges": {
    "biweekly-1": { "monthDays": [1, 14] },
    "biweekly-2": { "monthDays": [15, "last"] }
  },
  "projectMapping": {
    "my-app": {
      "default": "My App",
      "scopes": { "auth": "My App — Auth", "api": "My App — Backend" }
    }
  },
  "invoicing": { "hourlyRate": 85.00, "currency": "USD" }
}
```

Profiles live in the plugin's data directory (below). Managed via:

```
/timesheet --list-profiles
/timesheet --edit-profile my-profile
/timesheet --delete-profile my-profile
```

### Where your data lives

Profiles and custom templates are stored in, by priority:

1. `$GIT_TIMESHEET_HOME`, if you set it (e.g. a synced folder);
2. the plugin data directory Claude Code provides (`${CLAUDE_PLUGIN_DATA}`), which survives plugin updates;
3. `~/.config/git-timesheet/` (or `$XDG_CONFIG_HOME/git-timesheet/`) when the skill is installed by hand.

Versions up to 1.0.4 used `~/.claude/skills/timesheet/`. The skill notices old profiles there and offers to copy them over (nothing is deleted).

---

## Time tracker integrations

Push time entries directly to your tracking tool — no manual data entry:

| Service | Auth | What's pushed |
|---|---|---|
| **Toggl Track** | API token | Description, duration, project, date |
| **Clockify** | API key | Description, start/end time, project |
| **TMetric** | API token (Bearer) | Description, start/end time, project |
| **Harvest** | Personal access token + account ID | Description, hours, project, task, date |

Before pushing, you always get a confirmation showing exactly what will be created. Duplicate detection prevents double-entries if you run the same range again.

```
/timesheet --range first-half --push toggl
```

---

## Time & date formats

| Format | Example | Best for |
|---|---|---|
| **H:MM** | 5:30 | Default, international |
| **Decimal** | 5.5 | Invoicing, billing |
| **HH:MM:SS** | 05:30:00 | Precision tracking |
| **AM/PM** | 9:00 AM - 2:30 PM | US-style start/end times |

| Date format | Example |
|---|---|
| D MMM YYYY | 3 Mar 2026 |
| MMM D, YYYY | Mar 3, 2026 |
| DD/MM/YYYY | 15/03/2026 |
| MM/DD/YYYY | 03/15/2026 |
| YYYY-MM-DD | 2026-03-03 |

---

## Languages

All timesheet labels, headers, day names, and month names translate based on your `language` setting.

**Built-in:** English · Polish · German · French · Spanish · Dutch

For any other language, Claude writes a small translation file for the labels — just set the language code:

```json
{ "settings": { "language": "pt" } }
```

Holiday names stay in their native language (they're proper nouns).

---

## Security

- **API tokens are NEVER stored in profile files** and never pasted into the chat. They are read from environment variables at runtime.
- **Tokens never appear in output or on a command line**: a helper writes the auth header to a private (0600) temp file that `curl -H @file` reads, and deletes it afterwards.
- **Profiles only store non-secret config** (service name, workspace ID, settings) and live outside your repos, in the plugin data directory.
- **Confirmation before every API push** — you always see exactly what's being sent.

Set your tokens as environment variables:

**macOS / Linux (bash, zsh)** — add to `~/.bashrc` or `~/.zshrc`:

```bash
export GIT_TIMESHEET_TOGGL_TOKEN="your-token"
export GIT_TIMESHEET_CLOCKIFY_TOKEN="your-token"
export GIT_TIMESHEET_TMETRIC_TOKEN="your-token"
export GIT_TIMESHEET_HARVEST_TOKEN="your-token"
export GIT_TIMESHEET_HARVEST_ACCOUNT_ID="your-account-id"
```

**Windows (PowerShell)** — persistent (user-level):

```powershell
[System.Environment]::SetEnvironmentVariable('GIT_TIMESHEET_TOGGL_TOKEN', 'your-token', 'User')
[System.Environment]::SetEnvironmentVariable('GIT_TIMESHEET_CLOCKIFY_TOKEN', 'your-token', 'User')
[System.Environment]::SetEnvironmentVariable('GIT_TIMESHEET_TMETRIC_TOKEN', 'your-token', 'User')
[System.Environment]::SetEnvironmentVariable('GIT_TIMESHEET_HARVEST_TOKEN', 'your-token', 'User')
[System.Environment]::SetEnvironmentVariable('GIT_TIMESHEET_HARVEST_ACCOUNT_ID', 'your-account-id', 'User')
```

After setting, restart your terminal so Claude Code picks up the new variables.

---

## Requirements

- [Claude Code](https://code.claude.com) terminal CLI with plugin support
- Git repositories with commit history
- Python 3.9+ (standard library only) — macOS/Linux `python3`; on Windows `py -3`
- For PDF output: a headless Chromium — Python Playwright, Google Chrome/Chromium, or `npx -y playwright install chromium-headless-shell`. Without one you still get CSV and HTML, and the skill tells you what to install. The Playwright MCP plugin is an optional fallback.

---

## Contributing

PRs welcome. Some ideas the roadmap already has:

- More country holiday databases (India, Japan, Brazil, etc.)
- Monthly and bi-weekly timesheet layouts
- Dark mode template
- Jira / Linear ticket integration for richer task descriptions
- GitHub Actions integration for automated monthly timesheets

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Tests: `python3 -m unittest discover -s tests`.

---

## License

[MIT](LICENSE) — use commercially, modify, distribute. Just keep the copyright notice.

---

<div align="center">
  <sub>Built with <a href="https://code.claude.com">Claude Code</a>. Made by <a href="https://github.com/MarcinSufa">Marcin Sufa</a>.</sub>
</div>
