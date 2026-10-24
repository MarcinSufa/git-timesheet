#!/usr/bin/env python3
"""Render allocate.py output as CSV, HTML and/or PDF (one file per week).

Usage:
    python3 render.py --allocation alloc.json --format pdf|csv|html|both \\
        [--profile profile.json] [--out-dir ~/Downloads] [--lang pl] \\
        [--time-format H:MM|decimal|HH:MM:SS|AM/PM] [--date-format "D MMM YYYY"] \\
        [--billable yes|no] [--template default|NAME|PATH] [--labels labels.json] \\
        [--filename-pattern "Timesheet_{member}_Weekly_{startDate}_{endDate}"] \\
        [--rate 85 --currency USD] [--keep-html]

"both" = PDF + CSV. Settings default to the profile's "settings"; flags win.

PDF engines, tried in order (all headless Chromium, A4 landscape from the
template's @page rule):
  1. Python Playwright (`import playwright`) with its installed Chromium
  2. a Chrome/Chromium binary: $GIT_TIMESHEET_CHROME, PATH, macOS app bundles,
     or a Playwright browser cache (~/.cache/ms-playwright, $PLAYWRIGHT_BROWSERS_PATH),
     e.g. after `npx -y playwright install chromium-headless-shell`
If none works, the HTML is kept, CSV (if asked) is still written, and the
command exits 3 with install instructions.

Prints a JSON report: files, per-week stats, totals and (with --rate) invoice.
"""
import argparse
import csv
import datetime as dt
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import datadir  # noqa: E402

LABELS = {
    "en": {"title": "Weekly Timesheet", "member": "Member", "period": "Period",
           "totalTime": "Total Time", "timeEntries": "Time Entries", "billable": "Billable",
           "projects": "Projects", "total": "Total", "holiday": "Holiday", "pto": "PTO",
           "sick": "Sick", "noProject": "No project", "yes": "Yes", "no": "No",
           "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
           "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
                      "Oct", "Nov", "Dec"]},
    "pl": {"title": "Tygodniowa karta czasu pracy", "member": "Pracownik", "period": "Okres",
           "totalTime": "Czas całkowity", "timeEntries": "Wpisy czasu", "billable": "Rozliczane",
           "projects": "Projekty", "total": "Razem", "holiday": "Święto", "pto": "Urlop",
           "sick": "Chorobowe", "noProject": "Brak projektu", "yes": "Tak", "no": "Nie",
           "days": ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Ndz"],
           "months": ["Sty", "Lut", "Mar", "Kwi", "Maj", "Cze", "Lip", "Sie", "Wrz",
                      "Paź", "Lis", "Gru"]},
    "de": {"title": "Wochenarbeitszeittabelle", "member": "Mitarbeiter", "period": "Zeitraum",
           "totalTime": "Gesamtzeit", "timeEntries": "Zeiteinträge", "billable": "Abrechenbar",
           "projects": "Projekte", "total": "Gesamt", "holiday": "Feiertag", "pto": "Urlaub",
           "sick": "Krank", "noProject": "Kein Projekt", "yes": "Ja", "no": "Nein",
           "days": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
           "months": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep",
                      "Okt", "Nov", "Dez"]},
    "fr": {"title": "Feuille de temps hebdomadaire", "member": "Membre", "period": "Période",
           "totalTime": "Temps total", "timeEntries": "Entrées de temps", "billable": "Facturable",
           "projects": "Projets", "total": "Total", "holiday": "Jour férié", "pto": "Congé",
           "sick": "Maladie", "noProject": "Aucun projet", "yes": "Oui", "no": "Non",
           "days": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
           "months": ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep",
                      "Oct", "Nov", "Déc"]},
    "es": {"title": "Hoja de horas semanal", "member": "Miembro", "period": "Período",
           "totalTime": "Tiempo total", "timeEntries": "Entradas de tiempo",
           "billable": "Facturable", "projects": "Proyectos", "total": "Total",
           "holiday": "Festivo", "pto": "Vacaciones", "sick": "Enfermedad",
           "noProject": "Sin proyecto", "yes": "Sí", "no": "No",
           "days": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
           "months": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep",
                      "Oct", "Nov", "Dic"]},
    "nl": {"title": "Wekelijkse urenstaat", "member": "Medewerker", "period": "Periode",
           "totalTime": "Totale tijd", "timeEntries": "Tijdregistraties", "billable": "Facturabel",
           "projects": "Projecten", "total": "Totaal", "holiday": "Feestdag", "pto": "Verlof",
           "sick": "Ziek", "noProject": "Geen project", "yes": "Ja", "no": "Nee",
           "days": ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"],
           "months": ["Jan", "Feb", "Mrt", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep",
                      "Okt", "Nov", "Dec"]},
}

CSV_HEADER = ["User", "Time Entry", "Task", "Project", "Billable", "Tags", "Work Type", "Link"]


def labels_for(lang, override_file=None):
    base = dict(LABELS["en"])
    base.update(LABELS.get((lang or "en").lower(), {}))
    if override_file:
        with open(override_file, encoding="utf-8") as f:
            base.update(json.load(f))
    return base


# ------------------------------------------------------------------ formats

def norm_time_format(value):
    v = (value or "H:MM").strip().lower().replace(" ", "")
    if v in ("h:mm", "hmm"):
        return "H:MM"
    if v in ("decimal", "dec"):
        return "decimal"
    if v in ("hh:mm:ss", "hhmmss"):
        return "HH:MM:SS"
    if v in ("am/pm", "ampm", "usam/pm"):
        return "AM/PM"
    raise ValueError("unknown time format %r" % value)


def fmt_duration(minutes, time_format="H:MM"):
    """Duration in the chosen format (AM/PM shows durations as H:MM)."""
    if time_format == "decimal":
        return ("%.2f" % (minutes / 60.0)).rstrip("0").rstrip(".")
    if time_format == "HH:MM:SS":
        return "%02d:%02d:00" % divmod(minutes, 60)
    return "%d:%02d" % divmod(minutes, 60)


def fmt_clock(minutes_since_midnight):
    h, m = divmod(int(minutes_since_midnight), 60)
    suffix = "AM" if h % 24 < 12 else "PM"
    return "%d:%02d %s" % ((h % 12) or 12, m, suffix)


def parse_hhmm(s):
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def schedule_day(durations, day_start=9 * 60, lunch=(12 * 60, 13 * 60)):
    """Sequential (start, end) clock minutes; lunch is excluded from work time.

    A task that reaches the lunch break pauses for it, so its end time moves
    by the length of the break.
    """
    out, t = [], day_start
    ls, le = lunch if lunch else (None, None)
    for dur in durations:
        if ls is not None and ls <= t < le:
            t = le
        start, end = t, t + dur
        if ls is not None and start < ls < end:
            end += le - ls
        out.append((start, end))
        t = end
    return out


DATE_FORMATS = {
    "D MMM YYYY": lambda d, mon: "%d %s %d" % (d.day, mon, d.year),
    "MMM D, YYYY": lambda d, mon: "%s %d, %d" % (mon, d.day, d.year),
    "DD/MM/YYYY": lambda d, mon: d.strftime("%d/%m/%Y"),
    "MM/DD/YYYY": lambda d, mon: d.strftime("%m/%d/%Y"),
    "YYYY-MM-DD": lambda d, mon: d.isoformat(),
}


def fmt_date(iso, date_format, labels):
    d = dt.date.fromisoformat(iso)
    fn = DATE_FORMATS.get(date_format or "D MMM YYYY")
    if fn is None:
        raise ValueError("unknown date format %r (use one of: %s)"
                         % (date_format, ", ".join(DATE_FORMATS)))
    return fn(d, labels["months"][d.month - 1])


def off_label(day, labels):
    st = day["status"]
    if st == "holiday":
        return "%s: %s" % (labels["holiday"], day["label"]) if day.get("label") else labels["holiday"]
    if st in ("pto", "sick"):
        return day.get("label") or labels[st]
    return None


# ------------------------------------------------------------------ week model

def week_view(week, opts):
    """Cells per entry/day as strings, shared by CSV and HTML."""
    labels, tf = opts["labels"], opts["time_format"]
    days = week["days"]
    sched = {}
    if tf == "AM/PM":
        for d in days:
            todo = [(i, e["minutes"][d["date"]]) for i, e in enumerate(week["entries"])
                    if e["minutes"].get(d["date"])]
            for (i, _), span in zip(todo, schedule_day([m for _, m in todo], opts["day_start"],
                                                       opts["lunch"])):
                sched[(i, d["date"])] = span
    rows = []
    for i, e in enumerate(week["entries"]):
        cells = []
        for d in days:
            m = e["minutes"].get(d["date"], 0)
            if m and tf == "AM/PM":
                s, en = sched[(i, d["date"])]
                cells.append("%s - %s" % (fmt_clock(s), fmt_clock(en)))
            elif m:
                cells.append(fmt_duration(m, tf))
            else:
                cells.append(None)
        rows.append({"entry": e, "cells": cells, "total": fmt_duration(e["total"], tf)})
    totals = []
    for d in days:
        if d["status"] == "work":
            totals.append(fmt_duration(d["minutes"], tf))
        elif d["status"] in ("holiday", "pto", "sick"):
            totals.append(labels[d["status"]])
        else:
            totals.append("-")
    first = max(week["start"], opts["range_start"])
    last = min(week["end"], opts["range_end"])
    return {"rows": rows, "totals": totals, "first": first, "last": last,
            "total": fmt_duration(week["total"], tf)}


def render_csv(week, view, opts, path):
    labels = opts["labels"]
    days = week["days"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER + [d["date"] for d in days] + ["Total"])
        billable = "Yes" if opts["billable"] else "No"
        for row in view["rows"]:
            e = row["entry"]
            cells = []
            for d, c in zip(days, row["cells"]):
                cells.append(c if c is not None else (off_label(d, labels) or "-"))
            w.writerow([opts["member"], e["description"], "",
                        e["project"] or labels["noProject"], billable, "", "", ""]
                       + cells + [row["total"]])


def render_table(week, view, opts):
    labels, esc = opts["labels"], html.escape
    days = week["days"]
    out = ['<table class="timesheet">', "<thead><tr>",
           '<th class="col-entry">%s</th>' % esc(labels["timeEntries"]),
           '<th class="col-billable">%s</th>' % esc(labels["billable"]),
           '<th class="col-project">%s</th>' % esc(labels["projects"])]
    for d in days:
        head = '<div class="dow">%s</div><div class="date">%s</div>' % (
            esc(labels["days"][d["weekday"]]),
            esc(fmt_date(d["date"], opts["date_format"], labels)))
        if d["status"] in ("holiday", "pto", "sick"):
            head += '<div class="%s">%s</div>' % (
                d["status"], esc(d.get("label") or labels[d["status"]]))
        out.append('<th class="col-day">%s</th>' % head)
    out.append('<th class="col-total">%s</th></tr></thead><tbody>' % esc(labels["total"]))
    billable = labels["yes"] if opts["billable"] else labels["no"]
    for row in view["rows"]:
        e = row["entry"]
        out.append('<tr><td class="entry">%s</td><td class="billable">%s</td>'
                   '<td class="project">%s</td>' % (
                       esc(e["description"]), esc(billable),
                       esc(e["project"] or labels["noProject"])))
        for c in row["cells"]:
            out.append('<td class="day">%s</td>' % esc(c) if c else '<td class="day off">-</td>')
        out.append('<td class="total">%s</td></tr>' % esc(row["total"]))
    out.append('<tr class="totals-row"><td class="entry">%s</td><td></td><td></td>'
               % esc(labels["total"]))
    for d, t in zip(days, view["totals"]):
        cls = "day"
        if d.get("overtime"):
            cls += " overtime"
        elif d["status"] != "work":
            cls += " off"
        out.append('<td class="%s">%s</td>' % (cls, esc(t)))
    out.append('<td class="total">%s</td></tr></tbody></table>' % esc(view["total"]))
    return "\n".join(out)


def render_html(week, view, opts, template_text):
    labels, esc = opts["labels"], html.escape
    period = "%s – %s" % (fmt_date(view["first"], opts["date_format"], labels),
                          fmt_date(view["last"], opts["date_format"], labels))
    values = {
        "lang": esc(opts["lang"]), "title": esc(labels["title"]),
        "member_label": esc(labels["member"]), "member": esc(opts["member"]),
        "period_label": esc(labels["period"]), "period": esc(period),
        "total_label": esc(labels["totalTime"]), "total": esc(view["total"]),
        "table": render_table(week, view, opts),
    }
    return re.sub(r"\{\{\s*(\w+)\s*\}\}",
                  lambda m: values.get(m.group(1), m.group(0)), template_text)


def load_template(spec, plugin_data=None):
    if not spec or spec == "default":
        path = os.path.join(SKILL_DIR, "assets", "default.html")
    elif os.path.sep in spec or spec.endswith(".html"):
        path = os.path.expanduser(spec)
    else:
        path = os.path.join(datadir.resolve(plugin_data)[0], "templates", spec + ".html")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "{{table}}" not in text.replace(" ", ""):
        raise ValueError("template %s has no {{table}} placeholder (pre-1.1 template?); "
                         "see references/templates.md to convert it" % path)
    return text


# ------------------------------------------------------------------ PDF

def _cache_dirs():
    dirs = []
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        dirs.append(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    home = os.path.expanduser("~")
    dirs += [os.path.join(home, ".cache", "ms-playwright"),
             os.path.join(home, "Library", "Caches", "ms-playwright")]
    if os.environ.get("LOCALAPPDATA"):
        dirs.append(os.path.join(os.environ["LOCALAPPDATA"], "ms-playwright"))
    return dirs


def find_chrome():
    env = os.environ.get("GIT_TIMESHEET_CHROME")
    if env and os.path.isfile(env):
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
                 "chrome", "microsoft-edge"):
        p = shutil.which(name)
        if p:
            return p
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium"):
        if os.path.isfile(p):
            return p
    patterns = [
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell",
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell.exe",
        "chromium-*/chrome-linux*/chrome",
        "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
        "chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chromium-*/chrome-win*/chrome.exe",
    ]

    def revision(path):
        m = re.search(r"-(\d+)[/\\]", path)
        return int(m.group(1)) if m else 0

    for base in _cache_dirs():
        found = [p for pat in patterns for p in glob.glob(os.path.join(base, pat))
                 if os.access(p, os.X_OK)]
        if found:
            return max(found, key=revision)
    return None


def _pdf_python_playwright(html_files):
    from playwright.sync_api import sync_playwright  # noqa: optional dependency
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for src, dst in html_files:
            page.goto("file://" + os.path.abspath(src))
            page.pdf(path=dst, print_background=True, prefer_css_page_size=True)
        browser.close()


def _pdf_chrome(binary, html_files):
    with tempfile.TemporaryDirectory(prefix="git-timesheet-chrome-") as profile:
        for src, dst in html_files:
            # --no-sandbox matches Playwright's default launch; the page is our own
            # local HTML (all data escaped), and Ubuntu 24.04+ blocks the sandbox's
            # user namespaces for unprivileged binaries.
            cmd = [binary, "--headless", "--no-sandbox", "--disable-gpu", "--no-first-run",
                   "--user-data-dir=" + profile, "--no-pdf-header-footer",
                   "--print-to-pdf-no-header", "--print-to-pdf=" + os.path.abspath(dst),
                   "file://" + os.path.abspath(src)]
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if r.returncode != 0 or not _is_pdf(dst):
                raise RuntimeError("%s failed: %s" % (
                    os.path.basename(binary), r.stderr.decode("utf-8", "replace")[-500:]))


def _is_pdf(path):
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


PDF_HELP = """PDF output needs a working headless Chromium. Pick one, then run render.py again:
  - npx -y playwright install chromium-headless-shell   (~100 MB into the Playwright cache)
  - python3 -m pip install --user playwright && python3 -m playwright install chromium
  - install Google Chrome or Chromium, or set GIT_TIMESHEET_CHROME=/path/to/chrome
  - "error while loading shared libraries": sudo npx -y playwright install-deps chromium
  - or convert the kept HTML with the Playwright MCP (see references/pdf.md)"""


def to_pdf(html_files, engine="auto"):
    """Convert [(html, pdf)]; returns the engine name. Raises RuntimeError."""
    errors = []
    if engine in ("auto", "playwright"):
        try:
            _pdf_python_playwright(html_files)
            return "python-playwright"
        except ImportError:
            errors.append("python playwright: not installed")
        except Exception as e:  # browser missing, launch failure, ...
            errors.append("python playwright: %s" % str(e).splitlines()[0][:200])
    if engine in ("auto", "chrome"):
        binary = find_chrome()
        if binary:
            try:
                _pdf_chrome(binary, html_files)
                return "chrome:" + binary
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
                errors.append(str(e))
        else:
            errors.append("chrome/chromium: not found")
    raise RuntimeError("; ".join(errors) + "\n" + PDF_HELP)


# ------------------------------------------------------------------ main

def file_stem(pattern, member, first, last):
    safe = re.sub(r"[^\w.-]+", "_", member or "timesheet").strip("_")
    return (pattern.replace("{member}", safe)
            .replace("{startDate}", first.replace("-", ""))
            .replace("{endDate}", last.replace("-", "")))


def render(alloc, opts, formats, out_dir, template_text=None, keep_html=False, engine="auto"):
    os.makedirs(out_dir, exist_ok=True)
    report = {"files": [], "weeks": [], "warnings": [], "pdf_engine": None}
    pending_pdf = []
    tmp = tempfile.mkdtemp(prefix="git-timesheet-") if "pdf" in formats else None
    for week in alloc["weeks"]:
        if week["start"] > opts["range_end"] or week["end"] < opts["range_start"]:
            continue
        view = week_view(week, opts)
        stem = file_stem(opts["filename_pattern"], opts["member"], view["first"], view["last"])
        info = {"start": view["first"], "end": view["last"], "entries": len(week["entries"]),
                "total": view["total"], "total_minutes": week["total"],
                "work_days": sum(1 for d in week["days"] if d["status"] == "work"),
                "days_off": [{"date": d["date"], "type": d["status"],
                              "label": d.get("label") or opts["labels"][d["status"]]}
                             for d in week["days"] if d["status"] in ("holiday", "pto", "sick")],
                "needs_input": week.get("needs_input", []), "files": []}
        if "csv" in formats:
            p = os.path.join(out_dir, stem + ".csv")
            render_csv(week, view, opts, p)
            info["files"].append(p)
        if "html" in formats or "pdf" in formats:
            page = render_html(week, view, opts, template_text)
            if "html" in formats or keep_html:
                p = os.path.join(out_dir, stem + ".html")
                with open(p, "w", encoding="utf-8") as f:
                    f.write(page)
                info["files"].append(p)
            if "pdf" in formats:
                src = os.path.join(tmp, stem + ".html")
                with open(src, "w", encoding="utf-8") as f:
                    f.write(page)
                pending_pdf.append((src, os.path.join(out_dir, stem + ".pdf"), info))
        report["weeks"].append(info)
    if pending_pdf:
        try:
            report["pdf_engine"] = to_pdf([(s, d) for s, d, _ in pending_pdf], engine)
            for _, d, info in pending_pdf:
                info["files"].append(d)
        except RuntimeError as e:
            report["pdf_error"] = str(e)
            for s, _, info in pending_pdf:
                kept = os.path.join(out_dir, os.path.basename(s))
                shutil.copy(s, kept)
                if kept not in info["files"]:
                    info["files"].append(kept)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    report["files"] = [f for w in report["weeks"] for f in w["files"]]
    report["total_minutes"] = sum(w["total_minutes"] for w in report["weeks"])
    report["billable_minutes"] = report["total_minutes"] if opts["billable"] else 0
    report["needs_input"] = [d for w in report["weeks"] for d in w["needs_input"]]
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description="Render timesheets")
    p.add_argument("--allocation", required=True, help="allocate.py JSON (or - for stdin)")
    p.add_argument("--format", default=None, help="pdf, csv, html, both (pdf+csv); comma lists ok")
    p.add_argument("--profile")
    p.add_argument("--plugin-data", help='pass "${CLAUDE_PLUGIN_DATA}" (template lookup)')
    p.add_argument("--member")
    p.add_argument("--out-dir")
    p.add_argument("--lang")
    p.add_argument("--labels", help="JSON file overriding/adding label translations")
    p.add_argument("--time-format")
    p.add_argument("--date-format")
    p.add_argument("--billable", choices=["yes", "no"])
    p.add_argument("--template")
    p.add_argument("--filename-pattern")
    p.add_argument("--day-start", help="AM/PM mode, HH:MM (default 09:00)")
    p.add_argument("--lunch", help="AM/PM mode, HH:MM-HH:MM or 'none' (default 12:00-13:00)")
    p.add_argument("--rate", type=float, help="hourly rate for the invoice summary")
    p.add_argument("--currency")
    p.add_argument("--pdf-engine", choices=["auto", "playwright", "chrome"], default="auto")
    p.add_argument("--keep-html", action="store_true")
    a = p.parse_args(argv)

    profile = {}
    if a.profile:
        with open(os.path.expanduser(a.profile), encoding="utf-8") as f:
            profile = json.load(f)
    s = profile.get("settings", {})
    if a.allocation == "-":
        alloc = json.load(sys.stdin)
    else:
        with open(a.allocation, encoding="utf-8") as f:
            alloc = json.load(f)
    fmt = (a.format or s.get("outputFormat") or "pdf").lower()
    formats = set()
    for part in fmt.replace("+", ",").split(","):
        part = part.strip()
        formats |= {"pdf", "csv"} if part == "both" else {part}
    if not formats <= {"pdf", "csv", "html"}:
        p.error("unknown format in %r" % fmt)
    lunch_spec = a.lunch or (("%s-%s" % (s["lunchBreak"]["start"], s["lunchBreak"]["end"]))
                             if s.get("lunchBreak") else "12:00-13:00")
    try:
        lang = (a.lang or s.get("language") or "en").lower()
        opts = {
            "lang": lang,
            "labels": labels_for(lang, a.labels),
            "time_format": norm_time_format(a.time_format or s.get("timeFormat")),
            "date_format": a.date_format or s.get("dateFormat") or "D MMM YYYY",
            "billable": (a.billable or str(s.get("billable", "yes"))).lower() != "no",
            "member": a.member or alloc.get("member") or "",
            "filename_pattern": a.filename_pattern or s.get("filenamePattern")
            or "Timesheet_{member}_Weekly_{startDate}_{endDate}",
            "day_start": parse_hhmm(a.day_start or s.get("dayStartTime") or "09:00"),
            "lunch": None if lunch_spec == "none" else tuple(parse_hhmm(x) for x in lunch_spec.split("-")),
            "range_start": alloc["start"], "range_end": alloc["end"],
        }
        fmt_date(alloc["start"], opts["date_format"], opts["labels"])  # validate early
        template = None
        if formats & {"pdf", "html"}:
            template = load_template(a.template or s.get("template"), a.plugin_data)
    except (ValueError, OSError) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2
    out_dir = os.path.expanduser(a.out_dir or s.get("outputDir") or "~/Downloads")
    report = render(alloc, opts, formats, out_dir, template, a.keep_html, a.pdf_engine)
    rate = a.rate if a.rate is not None else (profile.get("invoicing") or {}).get("hourlyRate")
    if rate is not None:
        hours = report["billable_minutes"] / 60.0
        report["invoice"] = {"hours": round(hours, 2), "rate": rate,
                             "currency": a.currency or (profile.get("invoicing") or {}).get("currency"),
                             "amount": round(hours * float(rate), 2)}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report.get("pdf_error"):
        print(report["pdf_error"], file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
