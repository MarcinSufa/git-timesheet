import contextlib
import csv
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

import helpers
import allocate
import render


def sample_alloc():
    commits = [
        {"date": "2026-04-01", "sha": "a1", "insertions": 300, "deletions": 0, "files": 5,
         "scope": "auth", "repo": "app", "description": "feat(auth): <script>alert(1)</script>"},
        {"date": "2026-04-01", "sha": "b2", "insertions": 20, "deletions": 0, "files": 1,
         "scope": None, "repo": "app", "description": "fix: small"},
        {"date": "2026-04-02", "sha": "c3", "insertions": 50, "deletions": 0, "files": 2,
         "scope": None, "repo": "app", "description": "docs: guide"},
    ]
    doc = {"since": "2026-04-01", "until": "2026-04-03", "commits": commits}
    offs = allocate.parse_day_off("2026-04-03:pto")
    return allocate.allocate(doc, member="Jane Doe", country="PL", days_off=offs, seed=1,
                             mapping={"app": {"default": "My App"}})


def opts(**kw):
    o = {"lang": "en", "labels": render.labels_for("en"), "time_format": "H:MM",
         "date_format": "D MMM YYYY", "billable": True, "member": "Jane Doe",
         "filename_pattern": "Timesheet_{member}_Weekly_{startDate}_{endDate}",
         "day_start": 540, "lunch": (720, 780), "range_start": "2026-04-01",
         "range_end": "2026-04-03"}
    o.update(kw)
    return o


class FormatTest(unittest.TestCase):
    def test_durations(self):
        self.assertEqual(render.fmt_duration(330), "5:30")
        self.assertEqual(render.fmt_duration(45), "0:45")
        self.assertEqual(render.fmt_duration(330, "decimal"), "5.5")
        self.assertEqual(render.fmt_duration(45, "decimal"), "0.75")
        self.assertEqual(render.fmt_duration(480, "decimal"), "8")
        self.assertEqual(render.fmt_duration(330, "HH:MM:SS"), "05:30:00")
        self.assertEqual(render.norm_time_format("US AM/PM"), "AM/PM")
        with self.assertRaises(ValueError):
            render.norm_time_format("weird")

    def test_am_pm_schedule_excludes_lunch(self):
        spans = render.schedule_day([165, 315])
        self.assertEqual([(render.fmt_clock(a), render.fmt_clock(b)) for a, b in spans],
                         [("9:00 AM", "11:45 AM"), ("11:45 AM", "6:00 PM")])
        self.assertEqual(render.schedule_day([180, 60]), [(540, 720), (780, 840)])
        self.assertEqual(render.schedule_day([480], lunch=None), [(540, 1020)])

    def test_dates_localised(self):
        pl = render.labels_for("pl")
        self.assertEqual(render.fmt_date("2026-03-03", "D MMM YYYY", pl), "3 Mar 2026")
        self.assertEqual(render.fmt_date("2026-10-03", "D MMM YYYY", pl), "3 Paź 2026")
        en = render.labels_for("en")
        self.assertEqual(render.fmt_date("2026-03-03", "MMM D, YYYY", en), "Mar 3, 2026")
        self.assertEqual(render.fmt_date("2026-03-15", "DD/MM/YYYY", en), "15/03/2026")
        self.assertEqual(render.fmt_date("2026-03-15", "MM/DD/YYYY", en), "03/15/2026")
        with self.assertRaises(ValueError):
            render.fmt_date("2026-03-15", "YYYY.MM", en)

    def test_unknown_language_falls_back_and_labels_file_overrides(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"title": "Folha de horas semanal"}, f)
        try:
            pt = render.labels_for("pt", f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual(pt["title"], "Folha de horas semanal")
        self.assertEqual(pt["total"], "Total")

    def test_file_stem(self):
        self.assertEqual(render.file_stem("Timesheet_{member}_Weekly_{startDate}_{endDate}",
                                          "Jane O'Doe", "2026-04-01", "2026-04-05"),
                         "Timesheet_Jane_O_Doe_Weekly_20260401_20260405")


class RenderFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.alloc = sample_alloc()
        self.template = render.load_template("default")

    def tearDown(self):
        self.tmp.cleanup()

    def test_csv(self):
        rep = render.render(self.alloc, opts(), {"csv"}, self.tmp.name)
        self.assertEqual(len(rep["files"]), 1)
        with open(rep["files"][0], newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0][:8], render.CSV_HEADER)
        self.assertEqual(rows[0][8:], ["2026-03-30", "2026-03-31", "2026-04-01", "2026-04-02",
                                       "2026-04-03", "2026-04-04", "2026-04-05", "Total"])
        body = rows[1:]
        self.assertTrue(all(r[0] == "Jane Doe" and r[4] == "Yes" and r[3] == "My App"
                            for r in body))
        self.assertTrue(all(r[12] == "PTO" for r in body))  # day off shows the reason
        total = sum(int(r[-1].split(":")[0]) * 60 + int(r[-1].split(":")[1]) for r in body)
        self.assertEqual(total, 16 * 60)
        self.assertEqual(rep["weeks"][0]["days_off"][0]["type"], "pto")
        self.assertEqual(rep["billable_minutes"], 16 * 60)

    def test_billable_no(self):
        rep = render.render(self.alloc, opts(billable=False), {"csv"}, self.tmp.name)
        with open(rep["files"][0], newline="", encoding="utf-8") as f:
            self.assertTrue(all(r[4] == "No" for r in list(csv.reader(f))[1:]))
        self.assertEqual(rep["billable_minutes"], 0)

    def test_html_is_a_real_table_and_escapes_data(self):
        rep = render.render(self.alloc, opts(lang="pl", labels=render.labels_for("pl")),
                            {"html"}, self.tmp.name, self.template)
        with open(rep["files"][0], encoding="utf-8") as f:
            page = f.read()
        self.assertIn('<table class="timesheet">', page)
        self.assertIn("Tygodniowa karta czasu pracy", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>alert", page)
        self.assertIn('<div class="pto">Urlop</div>', page)
        self.assertNotIn("{{", page)
        self.assertEqual(page.count('<tr class="totals-row">'), 1)

    def test_template_without_table_placeholder_is_rejected(self):
        path = os.path.join(self.tmp.name, "old.html")
        with open(path, "w") as f:
            f.write("<html><body><table></table></body></html>")
        with self.assertRaises(ValueError):
            render.load_template(path)

    def test_pdf_with_fake_chrome(self):
        fake = os.path.join(self.tmp.name, "fake-chrome")
        with open(fake, "w") as f:
            f.write("#!%s\nimport sys\nfor a in sys.argv:\n"
                    "    if a.startswith('--print-to-pdf='):\n"
                    "        open(a.split('=', 1)[1], 'wb').write(b'%%PDF-1.4 fake')\n"
                    "open(sys.argv[0] + '.args', 'w').write(' '.join(sys.argv[1:]))\n"
                    % sys.executable)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        out = os.path.join(self.tmp.name, "out")
        with mock.patch.dict(os.environ, {"GIT_TIMESHEET_CHROME": fake}):
            rep = render.render(self.alloc, opts(), {"pdf"}, out, self.template, engine="chrome")
        self.assertTrue(rep["pdf_engine"].startswith("chrome:"))
        self.assertEqual(len(rep["files"]), 1)
        self.assertTrue(rep["files"][0].endswith(".pdf"))
        self.assertEqual(os.listdir(out), [os.path.basename(rep["files"][0])])  # no html left
        with open(fake + ".args") as f:
            args = f.read()
        self.assertIn("--headless", args)
        self.assertIn("--user-data-dir=", args)

    def test_pdf_failure_keeps_html_and_explains(self):
        with mock.patch.object(render, "find_chrome", return_value=None):
            rep = render.render(self.alloc, opts(), {"pdf", "csv"}, self.tmp.name,
                                self.template, engine="chrome")
        self.assertIn("pdf_error", rep)
        self.assertIn("playwright install", rep["pdf_error"])
        self.assertEqual(sorted(os.path.splitext(f)[1] for f in rep["files"]), [".csv", ".html"])

    @unittest.skipUnless(os.environ.get("GIT_TIMESHEET_TEST_PDF"), "set GIT_TIMESHEET_TEST_PDF=1")
    def test_real_pdf(self):
        rep = render.render(self.alloc, opts(), {"pdf"}, self.tmp.name, self.template)
        self.assertNotIn("pdf_error", rep, rep.get("pdf_error"))
        with open(rep["files"][0], "rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")


class FindChromeTest(unittest.TestCase):
    def test_playwright_cache_highest_revision(self):
        with tempfile.TemporaryDirectory() as cache:
            paths = []
            for rev in ("1208", "1248"):
                d = os.path.join(cache, "chromium_headless_shell-" + rev,
                                 "chrome-headless-shell-linux64")
                os.makedirs(d)
                p = os.path.join(d, "chrome-headless-shell")
                open(p, "w").close()
                os.chmod(p, 0o755)
                paths.append(p)
            env = {"PLAYWRIGHT_BROWSERS_PATH": cache, "PATH": "/nonexistent",
                   "HOME": cache}
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch("os.path.isfile", return_value=False):
                self.assertEqual(render.find_chrome(), paths[1])


class CliTest(unittest.TestCase):
    def test_csv_with_invoice(self):
        with tempfile.TemporaryDirectory() as tmp:
            apath = os.path.join(tmp, "a.json")
            with open(apath, "w") as f:
                json.dump(sample_alloc(), f)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = render.main(["--allocation", apath, "--format", "csv", "--out-dir", tmp,
                                    "--rate", "85", "--currency", "USD"])
            self.assertEqual(code, 0)
            rep = json.loads(out.getvalue())
            self.assertEqual(rep["invoice"], {"hours": 16.0, "rate": 85.0, "currency": "USD",
                                              "amount": 1360.0})

    def test_bad_date_format_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            apath = os.path.join(tmp, "a.json")
            with open(apath, "w") as f:
                json.dump(sample_alloc(), f)
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                code = render.main(["--allocation", apath, "--format", "csv", "--out-dir", tmp,
                                    "--date-format", "nope"])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
