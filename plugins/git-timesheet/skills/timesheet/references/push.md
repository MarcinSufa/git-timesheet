# Push to a time tracker (optional)

Supported: Toggl Track, Clockify, TMetric, Harvest. Push only after the files
are generated and the user confirmed.

## Tokens: environment variables only

- **Never ask the user to paste a token into the chat**, never write one into a
  profile, a file in the repo, or a command line, and never print one — not
  even its first characters.
- The user sets the variables in their shell profile and restarts Claude Code:

  ```bash
  # ~/.bashrc, ~/.zshrc (Windows: setx NAME value, or the PowerShell profile)
  export GIT_TIMESHEET_TOGGL_TOKEN="..."        # Toggl: Profile settings → API Token
  export GIT_TIMESHEET_CLOCKIFY_TOKEN="..."     # Clockify: Profile settings → API
  export GIT_TIMESHEET_TMETRIC_TOKEN="..."      # TMetric: My Profile → API tokens
  export GIT_TIMESHEET_HARVEST_TOKEN="..."      # Harvest: Developers → Personal Access Token
  export GIT_TIMESHEET_HARVEST_ACCOUNT_ID="..." # shown next to that token
  ```

- Check presence without revealing anything:
  `python3 "${CLAUDE_SKILL_DIR}/scripts/auth_header.py" --check toggl` prints
  `set` or `missing: VAR`.
- `auth_header.py SERVICE` writes the auth headers to a new mode-0600 temp file
  and prints only its path. `curl -H @file` reads them (curl 7.55+), so the
  token is never in curl's argv (`ps`, shell history) or in the transcript.
  Create the file, use it and delete it in the **same** Bash command.

## Entries and payloads

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/push_entries.py" --allocation "$WORK/alloc.json" \
  --profile "<profile.json>" --service toggl --workspace-id 123456 \
  [--project-ids "$WORK/project-ids.json"] > "$WORK/entries.json"
```

Each item has the date, description, project, minutes/hours, start/end times
(back to back from `dayStartTime`, lunch skipped) and `payload`, the request
body for the chosen service. `--project-ids` maps the profile's project names
to the service's IDs, which you look up first (below); unknown names push
without a project (Harvest requires one: ask the user).

Before pushing, confirm:

> Ready to push {N} time entries to {service} for {date range}.
>
> A) Push all entries
> B) Let me review first (shows entries in a table)
> C) Cancel — just keep the files

## Request pattern

Shell variables do not survive between Bash calls: start each command with
`WORK=<the work dir from SKILL.md step 4>`. Write each payload to a file and
send it with `-d @file`:

```bash
HDR=$(python3 "${CLAUDE_SKILL_DIR}/scripts/auth_header.py" toggl) || exit 1
trap 'rm -f "$HDR"' EXIT
python3 - "$WORK/entries.json" "$WORK/payloads" <<'PY'
import json, os, sys
os.makedirs(sys.argv[2], exist_ok=True)
for i, e in enumerate(json.load(open(sys.argv[1]))):
    json.dump(e["payload"], open(os.path.join(sys.argv[2], "%03d.json" % i), "w"))
PY
for f in "$WORK"/payloads/*.json; do
  code=$(curl -sS -o "$f.resp" -w '%{http_code}' -H @"$HDR" \
    -H "Content-Type: application/json" -X POST "$URL" -d @"$f")
  echo "$(basename "$f") $code"
done
```

Report the status codes, not the response bodies of auth errors.

| Service | Base URL | `$URL` for create | Auth headers (from `auth_header.py`) |
|---|---|---|---|
| Toggl Track | `https://api.track.toggl.com/api/v9` | `/workspaces/{workspaceId}/time_entries` | Basic `token:api_token` |
| Clockify | `https://api.clockify.me/api/v1` | `/workspaces/{workspaceId}/time-entries` | `X-Api-Key` |
| TMetric | `https://app.tmetric.com/api` | `/accounts/{accountId}/timeentries` | Bearer |
| Harvest | `https://api.harvestapp.com/v2` | `/time_entries` | Bearer + `Harvest-Account-Id` + `User-Agent` |

Lookups (GET with the same `-H @"$HDR"`):

- Toggl: workspaces `GET /me?with_related_data=true` → `workspaces[].id`;
  projects `GET /workspaces/{wid}/projects` → match by name.
- Clockify: workspace `GET /user` → `activeWorkspace`; projects
  `GET /workspaces/{wid}/projects` → match by name.
- TMetric: accounts `GET /accounts` → `[].id`; projects
  `GET /accounts/{id}/timeentries/projects` → match by name.
- Harvest: account `GET /users/me`; projects `GET /projects` → match by name;
  task `GET /projects/{id}/task_assignments` → the default task.

Payload fields per service (built by `push_entries.py`):

- Toggl: `description`, `start` (with UTC offset), `duration` (seconds),
  `workspace_id`, `project_id`, `created_with: "git-timesheet"`.
- Clockify: `start`/`end` (UTC, `Z`), `description`, `projectId`.
- TMetric: `startTime`/`endTime` (local, no offset), `note`, `projectId`.
- Harvest: `project_id`, `task_id` (both required), `spent_date`, `hours`
  (decimal), `notes`.

## Errors

- **401/403**: the token is wrong or expired. Ask the user to update the
  environment variable and restart Claude Code; do not ask for the token.
- **429**: wait and retry with 1 s, 2 s, 4 s delays.
- **Duplicates**: before pushing, list existing entries for the range. If any:
  > Found {N} existing entries in {service} for this date range.
  >
  > A) Skip duplicates — only push new entries
  > B) Replace all — delete existing and push fresh
  > C) Cancel push
- **Partial failure**: report which entries succeeded and which failed (status
  code and the error message from the response).

## Post-push report

```
Pushed 28 time entries to Toggl Track:

  Week of 2-8 Mar: 7 entries pushed
  Week of 9-15 Mar: 8 entries pushed

  0 skipped (duplicates)
  0 failed

Toggl workspace: My Company (ID: 123456)
```
