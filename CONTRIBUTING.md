# Contributing to git-timesheet

Thanks for your interest in contributing!

## How This Plugin Works

git-timesheet is a Claude Code skill defined entirely in `skills/timesheet/SKILL.md`. There is no runtime code — the SKILL.md is a set of instructions that Claude follows when you invoke `/timesheet`.

## How to Test Changes

1. Clone or symlink the repo into your Claude Code skills directory:
   ```bash
   ln -s /path/to/git-timesheet ~/.claude/skills/timesheet
   ```
2. Edit `skills/timesheet/SKILL.md`
3. Open a new Claude Code session
4. Run `/timesheet` and verify the behavior

There is no test suite — testing means invoking the skill and checking the output.

## What to Contribute

### Easy wins
- Add holidays for a new country (see the Python holiday script in SKILL.md)
- Fix a holiday date that's wrong for a specific year
- Improve commit message cleanup rules
- Fix typos or unclear instructions in the SKILL.md

### Medium effort
- Add a new time tracker API integration (see existing Toggl/Clockify/TMetric/Harvest specs)
- Add a new output format (e.g., Excel)
- Improve the complexity scoring algorithm

### Guidelines
- Keep the SKILL.md readable — it's instructions for an AI, not code
- Test your changes with a real `/timesheet` invocation before submitting a PR
- Don't add personal data, API keys, or real company names in examples
- Use generic placeholder data (Jane Doe, Acme App, etc.)

## Submitting a PR

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Test with `/timesheet` in Claude Code
5. Open a PR with a clear description of what changed and why
