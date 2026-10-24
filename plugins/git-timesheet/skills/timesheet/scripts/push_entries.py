#!/usr/bin/env python3
"""Flatten allocate.py output into time entries for a time-tracker push.

Usage:
    python3 push_entries.py --allocation alloc.json [--profile profile.json] \\
        [--day-start 09:00] [--lunch 12:00-13:00|none] [--tz-offset=+02:00] \\
        [--service toggl|clockify|tmetric|harvest --workspace-id ID --project-ids ids.json]

Prints a JSON list, one item per entry and day, in day order:
    {"date", "description", "project", "repo", "minutes", "seconds", "hours",
     "start_local", "end_local",   # 2026-03-03T09:00:00 (no offset; TMetric)
     "start", "end",               # with offset, 2026-03-03T09:00:00+01:00 (Toggl)
     "start_utc", "end_utc"}       # 2026-03-03T08:00:00Z (Clockify)

With --service every item also gets "payload", the JSON body for that
service's create-time-entry call (see references/push.md). --project-ids maps
project names to the service's IDs: {"My App": 123} or, for Harvest,
{"My App": {"project_id": 1, "task_id": 2}}. Unknown names give null.

Entries of a day run back to back from the day start; the lunch break is
skipped (same schedule as the AM/PM time format). The offset is the local
time zone of this machine on that date unless --tz-offset is given.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import parse_hhmm, schedule_day  # noqa: E402


def _offset(value):
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", value.strip())
    if not m:
        raise ValueError("tz offset must look like +02:00, got %r" % value)
    delta = dt.timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    return dt.timezone(-delta if m.group(1) == "-" else delta)


def entries(alloc, day_start=540, lunch=(720, 780), tz=None):
    out = []
    for week in alloc["weeks"]:
        for day in week["days"]:
            iso = day["date"]
            todo = [e for e in week["entries"] if e["minutes"].get(iso)]
            if not todo:
                continue
            spans = schedule_day([e["minutes"][iso] for e in todo], day_start, lunch)
            base = dt.datetime.fromisoformat(iso)
            for e, (a, b) in zip(todo, spans):
                start, end = base + dt.timedelta(minutes=a), base + dt.timedelta(minutes=b)
                zs = start.replace(tzinfo=tz) if tz else start.astimezone()
                ze = end.replace(tzinfo=tz) if tz else end.astimezone()
                minutes = e["minutes"][iso]
                out.append({
                    "date": iso, "description": e["description"], "project": e.get("project"),
                    "repo": e.get("repo"), "minutes": minutes, "seconds": minutes * 60,
                    "hours": round(minutes / 60.0, 2),
                    "start_local": start.isoformat(), "end_local": end.isoformat(),
                    "start": zs.isoformat(), "end": ze.isoformat(),
                    "start_utc": zs.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_utc": ze.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
    return out


def payload(service, e, workspace_id=None, ids=None):
    ref = (ids or {}).get(e["project"]) if e.get("project") else None
    if service == "toggl":
        return {"description": e["description"], "start": e["start"], "duration": e["seconds"],
                "workspace_id": int(workspace_id), "project_id": ref,
                "created_with": "git-timesheet"}
    if service == "clockify":
        return {"start": e["start_utc"], "end": e["end_utc"], "description": e["description"],
                "projectId": ref}
    if service == "tmetric":
        return {"startTime": e["start_local"], "endTime": e["end_local"],
                "note": e["description"], "projectId": ref}
    if service == "harvest":
        ref = ref or {}
        return {"project_id": ref.get("project_id"), "task_id": ref.get("task_id"),
                "spent_date": e["date"], "hours": e["hours"], "notes": e["description"]}
    raise ValueError("unknown service %r" % service)


def main(argv=None):
    p = argparse.ArgumentParser(description="Time entries for a time-tracker push")
    p.add_argument("--allocation", required=True)
    p.add_argument("--profile")
    p.add_argument("--day-start")
    p.add_argument("--lunch")
    p.add_argument("--tz-offset")
    p.add_argument("--service", choices=["toggl", "clockify", "tmetric", "harvest"])
    p.add_argument("--workspace-id", help="Toggl workspace ID (required for toggl)")
    p.add_argument("--project-ids", help="JSON file: project name -> service ID")
    a = p.parse_args(argv)
    if a.service == "toggl" and not a.workspace_id:
        p.error("--service toggl needs --workspace-id")
    s = {}
    if a.profile:
        with open(os.path.expanduser(a.profile), encoding="utf-8") as f:
            s = json.load(f).get("settings", {})
    with open(a.allocation, encoding="utf-8") as f:
        alloc = json.load(f)
    try:
        lunch_spec = a.lunch or (("%s-%s" % (s["lunchBreak"]["start"], s["lunchBreak"]["end"]))
                                 if s.get("lunchBreak") else "12:00-13:00")
        lunch = None if lunch_spec == "none" else tuple(parse_hhmm(x) for x in lunch_spec.split("-"))
        out = entries(alloc, parse_hhmm(a.day_start or s.get("dayStartTime") or "09:00"), lunch,
                      _offset(a.tz_offset) if a.tz_offset else None)
        if a.service:
            ids = {}
            if a.project_ids:
                with open(a.project_ids, encoding="utf-8") as f:
                    ids = json.load(f)
            for e in out:
                e["payload"] = payload(a.service, e, a.workspace_id, ids)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
