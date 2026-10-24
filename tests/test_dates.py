import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import unittest

import helpers  # noqa: F401
import dates

D = dt.date


class PresetTest(unittest.TestCase):
    def test_halves_and_months(self):
        today = D(2026, 2, 20)
        self.assertEqual(dates.preset("first-half", today), {"start": "2026-02-01", "end": "2026-02-15"})
        self.assertEqual(dates.preset("second-half", today), {"start": "2026-02-16", "end": "2026-02-28"})
        self.assertEqual(dates.preset("full-month:2028-02", today), {"start": "2028-02-01", "end": "2028-02-29"})
        self.assertEqual(dates.preset("second-half:march", today), {"start": "2026-03-16", "end": "2026-03-31"})
        self.assertEqual(dates.preset("first-half:apr", today)["start"], "2026-04-01")
        self.assertEqual(dates.preset("last-month", D(2026, 1, 10)), {"start": "2025-12-01", "end": "2025-12-31"})

    def test_weeks(self):
        thu = D(2026, 4, 9)
        self.assertEqual(dates.preset("this-week", thu), {"start": "2026-04-06", "end": "2026-04-12"})
        self.assertEqual(dates.preset("last-week", thu), {"start": "2026-03-30", "end": "2026-04-05"})

    def test_errors(self):
        for bad in ("fortnight", "last-week:march", "full-month:smarch"):
            with self.assertRaises(ValueError):
                dates.preset(bad, D(2026, 4, 9))

    def test_custom_ranges(self):
        today = D(2026, 4, 9)
        cr = {"biweekly-1": {"monthDays": [1, 14]}, "tail": {"monthDays": [15, "last"]},
              "q": {"monthRange": ["jan", "mar"]}, "prev": {"weekOffset": -1}}
        self.assertEqual(dates.resolve("biweekly-1", today, cr), {"start": "2026-04-01", "end": "2026-04-14"})
        self.assertEqual(dates.resolve("tail", today, cr)["end"], "2026-04-30")
        self.assertEqual(dates.resolve("q", today, cr), {"start": "2026-01-01", "end": "2026-03-31"})
        self.assertEqual(dates.resolve("prev", today, cr), {"start": "2026-03-30", "end": "2026-04-05"})
        with self.assertRaises(ValueError):
            dates.custom({"days": 3}, today)


class MenuTest(unittest.TestCase):
    def labels(self, m):
        return [o["label"] for o in m["options"]]

    def test_second_half_in_progress(self):
        m = dates.menu(D(2026, 4, 20))
        self.assertEqual(self.labels(m), ["Second half of this month", "First half of this month",
                                          "Last month"])
        self.assertEqual(m["options"][0]["end"], "2026-04-30")
        self.assertEqual(m["options"][2]["start"], "2026-03-01")

    def test_first_half_in_progress_crosses_year(self):
        m = dates.menu(D(2026, 1, 15))
        self.assertEqual(self.labels(m)[:2], ["First half of this month", "Second half of last month"])
        self.assertEqual(m["options"][1], {"start": "2025-12-16", "end": "2025-12-31",
                                           "label": "Second half of last month"})

    def test_custom_range_is_option_three(self):
        m = dates.menu(D(2026, 4, 3), {"biweekly-1": {"monthDays": [1, 14]}})
        self.assertEqual(m["options"][2]["label"], "biweekly-1")

    def test_weekly_only_when_preferred(self):
        self.assertNotIn("This week", self.labels(dates.menu(D(2026, 4, 3))))
        self.assertEqual(self.labels(dates.menu(D(2026, 4, 3), prefer_weekly=True))[:2],
                         ["This week", "Last week"])


class InfoTest(unittest.TestCase):
    def test_working_days_and_weeks(self):
        out = dates.info(D(2026, 4, 1), D(2026, 4, 15), country="PL")
        self.assertEqual(out["working_days"], 10)  # Easter Monday 6 Apr
        self.assertEqual([w["start"] for w in out["weeks"]], ["2026-03-30", "2026-04-06", "2026-04-13"])
        self.assertEqual(out["days_off"][0]["date"], "2026-04-06")
        self.assertEqual(out["start_weekday"], "Wed")

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            prof = os.path.join(tmp, "p.json")
            with open(prof, "w") as f:
                json.dump({"settings": {"preferWeekly": True}}, f)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(dates.main(["menu", "--today", "2026-04-09", "--profile", prof]), 0)
            self.assertEqual(json.loads(buf.getvalue())["options"][0]["label"], "This week")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(dates.main(["info", "2026-12-21", "2027-01-03", "--country", "pl",
                                         "--day-off", "2026-12-28..2026-12-31:pto"]), 0)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["working_days"], 3)  # 21-23 Dec; 24-25 Dec and 1 Jan are holidays
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dates.main(["info", "2026-04-10", "2026-04-01"]), 2)
            self.assertEqual(dates.main(["resolve", "nope"]), 2)


if __name__ == "__main__":
    unittest.main()
