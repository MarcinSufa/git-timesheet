#!/usr/bin/env python3
"""Date ranges for git-timesheet.

Usage:
    python3 dates.py menu    [--today 2026-04-20] [--profile p.json]
    python3 dates.py resolve NAME [--today ...] [--profile p.json]
    python3 dates.py info    START END [--country PL] [--work-days Mon,...] [--day-off 2026-04-07:pto]

menu     the three pre-computed options of the date-range question
resolve  a preset (first-half, second-half, full-month, last-month, this-week,
         last-week; first-half/second-half/full-month take an offset such as
         first-half:2026-03, second-half:march, full-month:mar) or a name from
         the profile's customRanges (monthDays, monthRange, weekOffset)
info     working-day count and the ISO weeks (one timesheet each) of a range

All output is JSON with ISO dates. Free-text dates ("1.04 to 15.04") are
parsed by the caller (see references/dates.md) and passed here as ISO.
"""
import argparse
import calendar
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allocate  # noqa: E402

DAY = dt.timedelta(days=1)
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
PRESETS = ("first-half", "second-half", "full-month", "last-month", "this-week", "last-week")


def last_day(year, month):
    return calendar.monthrange(year, month)[1]


def _month(token, today):
    """'2026-03', 'march', 'mar', '3' -> (year, month)."""
    t = token.strip().lower()
    if "-" in t:
        y, m = t.split("-", 1)
        return int(y), int(m)
    if t in MONTHS:
        return today.year, MONTHS[t]
    if t.isdigit() and 1 <= int(t) <= 12:
        return today.year, int(t)
    raise ValueError("unknown month %r" % token)


def _rng(start, end, label=None):
    out = {"start": start.isoformat(), "end": end.isoformat()}
    if label:
        out["label"] = label
    return out


def preset(name, today):
    base, _, offset = name.partition(":")
    y, m = _month(offset, today) if offset else (today.year, today.month)
    if base == "first-half":
        return _rng(dt.date(y, m, 1), dt.date(y, m, 15))
    if base == "second-half":
        return _rng(dt.date(y, m, 16), dt.date(y, m, last_day(y, m)))
    if base == "full-month":
        return _rng(dt.date(y, m, 1), dt.date(y, m, last_day(y, m)))
    if offset:
        raise ValueError("preset %r takes no offset" % base)
    if base == "last-month":
        prev = today.replace(day=1) - DAY
        return _rng(prev.replace(day=1), prev)
    monday = today - dt.timedelta(days=today.weekday())
    if base == "this-week":
        return _rng(monday, monday + 6 * DAY)
    if base == "last-week":
        return _rng(monday - 7 * DAY, monday - DAY)
    raise ValueError("unknown preset %r" % name)


def custom(spec, today):
    if "monthDays" in spec:
        a, b = spec["monthDays"]
        b = last_day(today.year, today.month) if b == "last" else int(b)
        return _rng(dt.date(today.year, today.month, int(a)), dt.date(today.year, today.month, b))
    if "monthRange" in spec:
        (_, m1), (_, m2) = (_month(str(x), today) for x in spec["monthRange"])
        return _rng(dt.date(today.year, m1, 1), dt.date(today.year, m2, last_day(today.year, m2)))
    if "weekOffset" in spec:
        monday = today - dt.timedelta(days=today.weekday()) + 7 * int(spec["weekOffset"]) * DAY
        return _rng(monday, monday + 6 * DAY)
    raise ValueError("custom range needs monthDays, monthRange or weekOffset: %r" % spec)


def resolve(name, today, custom_ranges=None):
    custom_ranges = custom_ranges or {}
    if name in custom_ranges:
        return custom(custom_ranges[name], today)
    return preset(name, today)


def menu(today, custom_ranges=None, prefer_weekly=False):
    """Options 1-3 of the date-range question (option 4 is always Custom)."""
    if prefer_weekly:
        opts = [dict(preset("this-week", today), label="This week"),
                dict(preset("last-week", today), label="Last week")]
    elif today.day > 15:
        opts = [dict(preset("second-half", today), label="Second half of this month"),
                dict(preset("first-half", today), label="First half of this month")]
    else:
        prev = today.replace(day=1) - DAY
        opts = [dict(preset("first-half", today), label="First half of this month"),
                dict(preset("second-half:%d-%02d" % (prev.year, prev.month), today),
                     label="Second half of last month")]
    if custom_ranges:
        name = next(iter(custom_ranges))
        opts.append(dict(custom(custom_ranges[name], today), label=name))
    else:
        opts.append(dict(preset("last-month", today), label="Last month"))
    return {"today": today.isoformat(), "weekday": today.strftime("%A"), "options": opts}


def info(start, end, work_days=None, country=None, days_off=()):
    days = allocate.build_days(start, end, work_days or allocate.WEEKDAYS[:5], country, days_off)
    inside = [d for d in days if d["status"] != "outside"]
    # build_days starts on a Monday, so every 7th day opens an ISO week
    starts = sorted({days[i - i % 7]["date"] for i, d in enumerate(days)
                     if d["status"] != "outside"})
    return {
        "start": start.isoformat(), "start_weekday": start.strftime("%a"),
        "end": end.isoformat(), "end_weekday": end.strftime("%a"),
        "working_days": sum(1 for d in inside if d["status"] == "work"),
        "days_off": [{"date": d["date"], "type": d["status"], "label": d["label"]}
                     for d in inside if d["status"] in ("holiday", "pto", "sick")],
        "weeks": [{"start": s, "end": (dt.date.fromisoformat(s) + 6 * DAY).isoformat()}
                  for s in starts],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Date ranges for git-timesheet")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("menu", "resolve"):
        sp = sub.add_parser(name)
        if name == "resolve":
            sp.add_argument("name")
        sp.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
        sp.add_argument("--profile")
    sp = sub.add_parser("info")
    sp.add_argument("start", type=dt.date.fromisoformat)
    sp.add_argument("end", type=dt.date.fromisoformat)
    sp.add_argument("--country")
    sp.add_argument("--work-days")
    sp.add_argument("--day-off", action="append", default=[])
    a = p.parse_args(argv)
    try:
        if a.cmd == "info":
            if a.end < a.start:
                raise ValueError("end date is before start date")
            offs = [x for v in a.day_off for x in allocate.parse_day_off(v)]
            cc = a.country.upper() if a.country and a.country.upper() in allocate.hol.RULES else None
            out = info(a.start, a.end, a.work_days.split(",") if a.work_days else None, cc, offs)
        else:
            profile = {}
            if a.profile:
                with open(os.path.expanduser(a.profile), encoding="utf-8") as f:
                    profile = json.load(f)
            cr = profile.get("customRanges") or {}
            if a.cmd == "menu":
                out = menu(a.today, cr, bool((profile.get("settings") or {}).get("preferWeekly")))
            else:
                out = resolve(a.name, a.today, cr)
    except (ValueError, allocate.hol.UnsupportedYear) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
