#!/usr/bin/env python3
"""Allocate working hours to commits, one timesheet week at a time.

Usage:
    python3 collect.py ... > commits.json
    python3 allocate.py --commits commits.json [--profile profile.json] \\
        [--member "Jane Doe"] [--start 2026-04-01 --end 2026-04-15] \\
        [--hours-per-day 8] [--increment 15] [--work-days Mon,Tue,Wed,Thu,Fri] \\
        [--country PL] [--day-off 2026-04-07:pto] [--day-off 2026-04-09..2026-04-10:sick] \\
        [--allow-overtime --max-hours-per-day 10] [--seed 42]

Settings come from the profile's "settings" and "projectMapping" when
--profile is given; command-line flags override them.

Rules (references/allocation.md is the spec; this file is the implementation):
  * score = insertions + deletions + 10 * files, floor 20 per commit
  * weekend and day-off commits move to the nearest working day in the range
    (ties go to the earlier day); a sick day stays sick even with commits
  * commits with the same repo + conventional-commit scope on the same day
    become one entry
  * empty working days in a week that has work are filled first with whole
    entries from overloaded days, then by continuing the largest entry of the
    week on the empty day; a week with no commits at all is reported in
    "needs_input" (ask the user what they worked on)
  * every working day totals exactly hours-per-day; with 2+ entries each
    entry gets at least 1:00, the rest is shared in proportion to score
  * when 1:00 per entry does not fit, overtime (if allowed) raises the day to
    at most max-hours-per-day; otherwise the minimum drops to one increment
    and, if still needed, the two smallest entries are merged
  * deliberate variation: scores get a +-15% jitter and a two-entry day is
    never split evenly; the jitter comes from --seed (default: derived from
    member, range and commit ids, so the same input gives the same output)
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import holidays as hol  # noqa: E402  (our holidays.py, not the PyPI package)

DAY = dt.timedelta(days=1)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SCORE_FLOOR = 20
MIN_TASK_MINUTES = 60
JITTER = 0.15
MAX_DESC = 80


def score_of(commit):
    raw = int(commit.get("insertions", 0)) + int(commit.get("deletions", 0)) \
        + 10 * int(commit.get("files", 0))
    return max(SCORE_FLOOR, raw)


def _truncate(s, n=MAX_DESC):
    return s if len(s) <= n else s[: n - 3].rstrip() + "..."


def parse_day_off(value):
    """'2026-04-07', '2026-04-07:sick', '2026-04-07..2026-04-11:pto:Vacation'.

    Type 'holiday' ('2026-05-01:holiday:Labour Day') adds a public holiday by
    hand, for countries without a built-in calendar.
    """
    parts = value.split(":", 2)
    span = parts[0]
    kind = (parts[1] if len(parts) > 1 and parts[1] else "pto").lower()
    if kind not in ("pto", "sick", "holiday"):
        raise ValueError("day-off type must be pto, sick or holiday, got %r" % kind)
    reason = parts[2] if len(parts) > 2 else None
    if ".." in span:
        a, b = span.split("..", 1)
        first, last = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    else:
        first = last = dt.date.fromisoformat(span)
    out = []
    d = first
    while d <= last:
        out.append((d, kind, reason))
        d += DAY
    return out


def project_for(mapping, repo, scope):
    m = (mapping or {}).get(repo)
    if not m:
        return None
    if scope and scope in (m.get("scopes") or {}):
        return m["scopes"][scope]
    return m.get("default")


def default_seed(member, start, end, shas):
    h = hashlib.sha256()
    h.update(("%s|%s|%s|" % (member or "", start, end)).encode())
    for s in sorted(shas):
        h.update(s.encode())
    return int(h.hexdigest()[:8], 16)


# ------------------------------------------------------------------ calendar

def build_days(start, end, work_days, country, days_off):
    """Every date from the Monday before start to the Sunday after end."""
    first = start - dt.timedelta(days=start.weekday())
    last = end + dt.timedelta(days=6 - end.weekday())
    hmap = {}
    if country:
        for h in hol.holidays_between(first, last, country):
            hmap.setdefault(h["date"], []).append(h["name"])
    offmap = {d.isoformat(): (k, r) for d, k, r in days_off}
    days = []
    d = first
    while d <= last:
        iso = d.isoformat()
        label = None
        if d < start or d > end:
            status = "outside"
        elif WEEKDAYS[d.weekday()] not in work_days:
            status = "weekend"
            if iso in hmap:
                label = " / ".join(hmap[iso])
        elif iso in hmap:
            status, label = "holiday", " / ".join(hmap[iso])
        elif iso in offmap:
            status, label = offmap[iso][0], offmap[iso][1]
        else:
            status = "work"
        days.append({"date": iso, "weekday": d.weekday(), "status": status,
                     "label": label, "minutes": 0})
        d += DAY
    return days


def nearest_work_day(iso, work_isos):
    """Nearest working day to iso; ties go to the earlier day. None if none."""
    if not work_isos:
        return None
    d = dt.date.fromisoformat(iso)
    return min(work_isos, key=lambda w: (abs((dt.date.fromisoformat(w) - d).days), w))


# ---------------------------------------------------------------- allocation

def split_minutes(weights, total, increment, minimum, rng):
    """Integer minutes (multiples of increment) summing to total.

    Proportional to weights, each at least `minimum` (water-filling), rounded
    with the largest-remainder method. Two entries never get the same time.
    """
    n = len(weights)
    if n == 0:
        return []
    if n == 1:
        return [total]
    units, min_units = total // increment, minimum // increment
    fixed = [False] * n
    share = [0.0] * n
    while True:
        free = [i for i in range(n) if not fixed[i]]
        left = units - min_units * (n - len(free))
        wsum = sum(weights[i] for i in free) or 1.0
        changed = False
        for i in free:
            share[i] = left * weights[i] / wsum
            if share[i] < min_units:
                fixed[i], changed = True, True
        if not changed:
            break
    for i in range(n):
        if fixed[i]:
            share[i] = float(min_units)
    base = [int(s) for s in share]
    rest = units - sum(base)
    order = sorted(range(n), key=lambda i: (share[i] - base[i], weights[i]), reverse=True)
    for i in order[:rest]:
        base[i] += 1
    if n == 2 and base[0] == base[1] and units >= 2 * min_units + 2:
        big = 0 if weights[0] > weights[1] else 1 if weights[1] > weights[0] else rng.randrange(2)
        step = min(rng.choice([1, 2]), base[1 - big] - min_units)
        if step > 0:
            base[big] += step
            base[1 - big] -= step
    return [b * increment for b in base]


def allocate(commits_doc, start=None, end=None, member=None, hours_per_day=8,
             increment=15, work_days=None, country=None, days_off=(),
             allow_overtime=False, max_hours_per_day=10, mapping=None, seed=None):
    work_days = work_days or WEEKDAYS[:5]
    start = start or dt.date.fromisoformat(commits_doc["since"])
    end = end or dt.date.fromisoformat(commits_doc["until"])
    day_minutes = int(round(float(hours_per_day) * 60))
    if increment <= 0 or day_minutes % increment:
        raise ValueError("hours per day (%s) must be a multiple of the %d-minute increment"
                         % (hours_per_day, increment))
    max_minutes = int(round(float(max_hours_per_day) * 60)) if allow_overtime else day_minutes
    max_minutes = max(day_minutes, max_minutes - max_minutes % increment)
    commits = commits_doc.get("commits", [])
    if seed is None:
        seed = default_seed(member, start, end, [c.get("sha", "") for c in commits])
    rng = random.Random(seed)
    warnings = []

    days = build_days(start, end, work_days, country, days_off)
    by_date = {d["date"]: d for d in days}
    work_isos = [d["date"] for d in days if d["status"] == "work"]

    # 1. commits -> tasks on working days
    tasks = {}
    for c in commits:
        target = c["date"]
        if target not in by_date or by_date[target]["status"] != "work":
            target = nearest_work_day(c["date"], work_isos)
            if target is None:
                warnings.append("no working day in range for commit %s (%s); skipped"
                                % (c.get("sha", "")[:8], c.get("date")))
                continue
        scope = c.get("scope")
        key = (target, c.get("repo"), scope) if scope else (target, c.get("sha"), None)
        t = tasks.get(key)
        if t is None:
            t = tasks[key] = {"date": target, "repo": c.get("repo"), "scope": scope,
                              "descriptions": [], "shas": [], "score": 0}
        t["descriptions"].append((score_of(c), c.get("description") or c.get("subject", "")))
        t["shas"].append(c.get("sha"))
        t["score"] += score_of(c)
    day_tasks = {iso: [] for iso in work_isos}
    for t in tasks.values():
        seen, parts = set(), []
        for _, desc in sorted(t["descriptions"], key=lambda x: -x[0]):
            if desc not in seen:
                seen.add(desc)
                parts.append(desc)
        t["description"] = _truncate("; ".join(parts))
        del t["descriptions"]
        t["weight"] = t["score"] * rng.uniform(1 - JITTER, 1 + JITTER)
        day_tasks[t["date"]].append(t)

    # 2. per week: fill empty working days, flag weeks without any work
    weeks = []
    for i in range(0, len(days), 7):
        wdays = days[i:i + 7]
        wwork = [d["date"] for d in wdays if d["status"] == "work"]
        week = {"start": wdays[0]["date"], "end": wdays[-1]["date"], "days": wdays,
                "entries": [], "total": 0, "work_days": len(wwork), "needs_input": []}
        weeks.append(week)
        if not any(day_tasks[w] for w in wwork):
            week["needs_input"] = list(wwork)
            continue
        cap = max_minutes // MIN_TASK_MINUTES
        for empty in [w for w in wwork if not day_tasks[w]]:
            donors = [w for w in wwork if len(day_tasks[w]) > cap]
            if donors:
                donor = nearest_work_day(empty, donors)
                t = min(day_tasks[donor], key=lambda x: x["weight"])
                day_tasks[donor].remove(t)
                day_tasks[empty].append(t)
                continue
            src = max((t for w in wwork for t in day_tasks[w]),
                      key=lambda x: (x["weight"], x["date"]))
            half = dict(src, shas=list(src["shas"]))
            src["weight"] /= 2.0
            half["weight"] = src["weight"]
            day_tasks[empty].append(half)

    # 3. per day: minutes
    for d in days:
        if d["status"] != "work" or not day_tasks[d["date"]]:
            continue
        ts = day_tasks[d["date"]]
        total, minimum = day_minutes, MIN_TASK_MINUTES if len(ts) > 1 else increment
        if len(ts) * minimum > day_minutes:
            if allow_overtime and max_minutes > day_minutes:
                total = min(max_minutes, len(ts) * minimum)
            if len(ts) * minimum > total:
                minimum = max(increment, (total // len(ts)) // increment * increment)
            while len(ts) * minimum > total:
                ts.sort(key=lambda x: x["weight"])
                a, b = ts.pop(0), ts.pop(0)
                ts.append({"date": d["date"], "repo": b["repo"], "scope": b["scope"],
                           "description": _truncate(b["description"] + "; " + a["description"]),
                           "shas": b["shas"] + a["shas"], "score": a["score"] + b["score"],
                           "weight": a["weight"] + b["weight"]})
                warnings.append("%s: merged two small entries to fit the day" % d["date"])
        mins = split_minutes([t["weight"] for t in ts], total, increment, minimum, rng)
        for t, m in zip(ts, mins):
            t.setdefault("minutes", {})[d["date"]] = m
        d["minutes"] = total
        if total > day_minutes:
            d["overtime"] = True

    # 4. weekly rows: one row per description + project
    for week in weeks:
        rows = {}
        wd = {d["date"] for d in week["days"]}
        for iso in sorted(wd):
            for t in day_tasks.get(iso, []):
                project = project_for(mapping, t["repo"], t["scope"])
                key = (t["description"], project)
                r = rows.get(key)
                if r is None:
                    r = rows[key] = {"description": t["description"], "project": project,
                                     "repo": t["repo"], "scope": t["scope"], "shas": [],
                                     "minutes": {}, "total": 0}
                for s in t["shas"]:
                    if s not in r["shas"]:
                        r["shas"].append(s)
                for k, m in t.get("minutes", {}).items():
                    r["minutes"][k] = r["minutes"].get(k, 0) + m
        entries = [r for r in rows.values() if r["minutes"]]
        for r in entries:
            r["total"] = sum(r["minutes"].values())
        entries.sort(key=lambda r: (min(r["minutes"]), -r["total"]))
        week["entries"] = entries
        week["total"] = sum(d["minutes"] for d in week["days"])

    return {
        "member": member, "start": start.isoformat(), "end": end.isoformat(),
        "hours_per_day": hours_per_day, "increment": increment, "work_days": work_days,
        "country": country, "seed": seed, "weeks": weeks,
        "total_minutes": sum(w["total"] for w in weeks),
        "needs_input": [x for w in weeks for x in w["needs_input"]],
        "warnings": warnings,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Allocate hours to commits")
    p.add_argument("--commits", required=True, help="collect.py JSON file, or - for stdin")
    p.add_argument("--profile", help="profile JSON (settings + projectMapping)")
    p.add_argument("--member")
    p.add_argument("--start", type=dt.date.fromisoformat)
    p.add_argument("--end", type=dt.date.fromisoformat)
    p.add_argument("--hours-per-day", type=float)
    p.add_argument("--increment", type=int, help="minutes: 15, 30 or 60")
    p.add_argument("--work-days", help="comma list, e.g. Mon,Tue,Wed,Thu,Fri")
    p.add_argument("--country", help="holiday calendar (holidays.py code); 'none' for none")
    p.add_argument("--day-off", action="append", default=[],
                   help="DATE[..DATE][:pto|sick[:reason]] (repeatable)")
    p.add_argument("--allow-overtime", action="store_true", default=None)
    p.add_argument("--max-hours-per-day", type=float)
    p.add_argument("--seed", type=int)
    p.add_argument("--out", help="write JSON here instead of stdout")
    a = p.parse_args(argv)

    profile = {}
    if a.profile:
        with open(os.path.expanduser(a.profile), encoding="utf-8") as f:
            profile = json.load(f)
    s = profile.get("settings", {})
    if a.commits == "-":
        doc = json.load(sys.stdin)
    else:
        with open(a.commits, encoding="utf-8") as f:
            doc = json.load(f)
    country = a.country if a.country is not None else s.get("country")
    if country and country.lower() in ("none", "other", ""):
        country = None
    if country and country.upper() not in hol.RULES:
        print("WARNING: no built-in holidays for %r; pass them as --day-off" % country,
              file=sys.stderr)
        country = None
    days_off = []
    try:
        for v in a.day_off:
            days_off += parse_day_off(v)
        result = allocate(
            doc, start=a.start, end=a.end, member=a.member,
            hours_per_day=a.hours_per_day or s.get("hoursPerDay", 8),
            increment=a.increment or s.get("timeIncrement", 15),
            work_days=a.work_days.split(",") if a.work_days else s.get("workDays"),
            country=country.upper() if country else None,
            days_off=days_off,
            allow_overtime=a.allow_overtime if a.allow_overtime is not None
            else bool(s.get("allowOvertime", False)),
            max_hours_per_day=a.max_hours_per_day or s.get("maxHoursPerDay", 10),
            mapping=profile.get("projectMapping"), seed=a.seed)
    except (ValueError, hol.UnsupportedYear) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)
    for w in result["warnings"]:
        print("WARNING: " + w, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
