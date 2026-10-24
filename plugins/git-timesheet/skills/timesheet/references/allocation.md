# How hours are allocated

`scripts/allocate.py` implements these rules; this page is the specification.
Run it, do not allocate by hand.

1. **Score** per commit = insertions + deletions + 10 × files changed, at
   least 20 (even a one-line fix took investigation and testing).
2. **Move** commits made on a weekend, holiday, PTO or sick day to the nearest
   working day inside the range (a tie goes to the earlier day). A sick day
   stays sick even if it has commits.
3. **Group**: commits of the same repo and conventional-commit scope
   (`type(scope): ...`) on the same day become one entry; the largest commit's
   description comes first.
4. **Fill** every working day of a week that has work:
   - an empty day first takes whole entries from a day that has more entries
     than fit at 1:00 each;
   - otherwise it continues the week's largest entry.
   A week with no commits at all (and not fully off) is listed in
   `needs_input`: ask the user what they worked on.
5. **Split** each day to exactly `hoursPerDay`, in `timeIncrement` steps:
   - one entry takes the whole day;
   - two or more get at least 1:00 each and share the rest in proportion to
     score (largest-remainder rounding);
   - a two-entry day is never split evenly (no 4:00 + 4:00).
6. **Too many entries**: when 1:00 each does not fit, overtime (if allowed)
   raises the day to at most `maxHoursPerDay` and marks it as overtime;
   otherwise the minimum drops to one increment, and if even that does not fit,
   the two smallest entries are merged (with a warning).
7. **Variation**: scores get a ±15% jitter so splits look natural. The random
   seed defaults to a hash of member, range and commit SHAs, so the same input
   always gives the same timesheet; `--seed N` changes it.

Entry descriptions come from `collect.py`: PR numbers `(#123)` removed, a
trailing `Refs: ABC-123` moved into the text as `(ABC-123)`, GitHub's `…`
stripped, the first word after the colon capitalised, at most 80 characters.

Choices made where the 1.0.x instructions disagreed (1.1.0):

- The minimum of 1:00 applies to every entry on a day with 2+ entries (the
  "Allocate" rules), not only to 3+ entries.
- "Docs/config get less time than feature code" was dropped: time follows the
  score only.
- "Holiday week: reduce total hours" means holidays simply have no hours; the
  remaining working days still total `hoursPerDay` each.

Manual entries for `needs_input` weeks: add items to the `commits` list of
the collect JSON, e.g.
`{"repo": "my-app", "sha": "manual-1", "date": "2026-04-14", "description": "Code review", "scope": null, "insertions": 0, "deletions": 0, "files": 0}`
(one per task; the score floor makes each worth the same unless you set
`insertions` to weight them), then run `allocate.py` again.
