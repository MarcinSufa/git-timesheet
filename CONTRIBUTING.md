# Contributing to git-timesheet

Thanks for your interest in contributing!

## How This Plugin Works

git-timesheet is a Claude Code skill in `plugins/git-timesheet/skills/timesheet/`:

- `SKILL.md` — the conversation: which questions to ask, in which order, and which script to run;
- `references/*.md` — details Claude reads when needed (setup questions, profile schema, templates, dates, output, push, languages, allocation rules);
- `scripts/*.py` — the deterministic work, standard-library Python 3.9+: `collect.py` (git log), `holidays.py`, `dates.py`, `allocate.py`, `render.py` (CSV/HTML/PDF), `datadir.py`, `push_entries.py`, `auth_header.py`;
- `assets/default.html` — the built-in PDF template.

## How to Test Changes

Run the unit tests (no network, no Claude needed; they build throw-away git repos):

```bash
python3 -m unittest discover -s tests -v
```

A real PDF test is skipped unless a headless Chromium works on your machine:

```bash
GIT_TIMESHEET_TEST_PDF=1 python3 -m unittest discover -s tests -p "test_render.py"
```

Then try the skill itself in Claude Code, loading the plugin from your checkout:

```bash
claude --plugin-dir ./plugins/git-timesheet
```

Run `/timesheet` and check the output. CI runs the unit tests on every push and PR (`.github/workflows/test.yml`).

## What to Contribute

### Easy wins
- Add holidays for a new country (`scripts/holidays.py` + a test in `tests/test_holidays.py`)
- Fix a holiday date that's wrong for a specific year
- Improve commit message cleanup rules (`clean_subject` in `scripts/collect.py`)
- Fix typos or unclear instructions in `SKILL.md` or `references/`

### Medium effort
- Add a new time tracker API integration (`scripts/push_entries.py`, `scripts/auth_header.py`, `references/push.md`)
- Add a new output format (e.g., Excel) in `scripts/render.py`
- Improve the complexity scoring algorithm (`scripts/allocate.py`, spec in `references/allocation.md`)

### Guidelines
- Keep `SKILL.md` short and readable — it's instructions for an AI; put long details in `references/` and logic in `scripts/`
- Scripts use the Python standard library only and stay executable (`chmod +x`)
- Add or update tests for script changes
- Don't add personal data, API keys, or real company names in examples
- Use generic placeholder data (Jane Doe, Acme App, etc.)

## Submitting a PR

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Run the tests and try `/timesheet` in Claude Code
5. Open a PR with a clear description of what changed and why
