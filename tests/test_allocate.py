import contextlib
import datetime as dt
import io
import json
import os
import tempfile
import unittest

import helpers  # noqa: F401
import allocate

D = dt.date


def commit(date, sha, ins=10, files=1, scope=None, repo="app", desc=None):
    return {"date": date, "sha": sha, "insertions": ins, "deletions": 0, "files": files,
            "scope": scope, "repo": repo, "description": desc or "task %s" % sha}


def doc(commits, since="2026-04-06", until="2026-04-12"):
    return {"since": since, "until": until, "commits": commits}


def days_by_date(result):
    return {d["date"]: d for w in result["weeks"] for d in w["days"]}


def minutes_by_desc(result):
    out = {}
    for w in result["weeks"]:
        for e in w["entries"]:
            for k, v in e["minutes"].items():
                out.setdefault(e["description"], {})[k] = v
    return out


class ScoreTest(unittest.TestCase):
    def test_formula_and_floor(self):
        self.assertEqual(allocate.score_of({"insertions": 100, "deletions": 50, "files": 8}), 230)
        self.assertEqual(allocate.score_of({"insertions": 1, "deletions": 0, "files": 1}), 20)
        self.assertEqual(allocate.score_of({"insertions": 0, "deletions": 0, "files": 0}), 20)


class SplitMinutesTest(unittest.TestCase):
    def test_exact_total_and_increment(self):
        import random
        rng = random.Random(1)
        for weights in ([230, 13], [5, 5], [100, 50, 20, 20], [1] * 8, [1000, 1, 1]):
            mins = allocate.split_minutes(weights, 480, 15, 60, rng)
            self.assertEqual(sum(mins), 480)
            self.assertTrue(all(m % 15 == 0 and m >= 60 for m in mins), mins)

    def test_two_entries_never_even(self):
        import random
        for seed in range(30):
            a, b = allocate.split_minutes([50, 50], 480, 15, 60, random.Random(seed))
            self.assertNotEqual(a, b)

    def test_proportional(self):
        import random
        big, small = allocate.split_minutes([230, 20], 480, 15, 60, random.Random(0))
        self.assertEqual((big, small), (420, 60))


class AllocateTest(unittest.TestCase):
    def test_every_working_day_totals_exactly(self):
        commits = [commit("2026-04-%02d" % d, "s%d%d" % (d, i), ins=10 * (i + 1) * d)
                   for d in range(6, 11) for i in range(d % 3 + 1)]
        r = allocate.allocate(doc(commits))
        for d in r["weeks"][0]["days"]:
            self.assertEqual(d["minutes"], 480 if d["status"] == "work" else 0, d)
        self.assertEqual(r["total_minutes"], 5 * 480)
        for e in r["weeks"][0]["entries"]:
            for m in e["minutes"].values():
                self.assertEqual(m % 15, 0)

    def test_holidays_pto_sick_and_moved_commits(self):
        commits = [commit("2026-04-06", "easter"),     # PL Easter Monday
                   commit("2026-04-07", "a", ins=200),
                   commit("2026-04-08", "sick"),       # sick day keeps status
                   commit("2026-04-11", "sat"),        # Saturday -> Friday
                   commit("2026-04-12", "sun")]        # Sunday, last day of range -> Friday
        offs = allocate.parse_day_off("2026-04-08:sick") + allocate.parse_day_off("2026-04-09:pto")
        r = allocate.allocate(doc(commits), country="PL", days_off=offs)
        days = days_by_date(r)
        self.assertEqual(days["2026-04-06"]["status"], "holiday")
        self.assertEqual(days["2026-04-06"]["label"], "Poniedziałek Wielkanocny")
        self.assertEqual((days["2026-04-08"]["status"], days["2026-04-08"]["minutes"]), ("sick", 0))
        self.assertEqual((days["2026-04-09"]["status"], days["2026-04-09"]["minutes"]), ("pto", 0))
        m = minutes_by_desc(r)
        self.assertEqual(set(m["task easter"]), {"2026-04-07"})  # nearest, earlier on a tie
        self.assertEqual(set(m["task sick"]), {"2026-04-07"})
        self.assertEqual(set(m["task sat"]), {"2026-04-10"})
        self.assertEqual(set(m["task sun"]), {"2026-04-10"})
        self.assertEqual(r["weeks"][0]["total"], 2 * 480)

    def test_same_scope_same_day_is_one_entry(self):
        commits = [commit("2026-04-06", "a", scope="auth", desc="feat(auth): A"),
                   commit("2026-04-06", "b", scope="auth", desc="fix(auth): B"),
                   commit("2026-04-06", "c", scope="api", desc="feat(api): C")]
        r = allocate.allocate(doc(commits, until="2026-04-06"))
        entries = r["weeks"][0]["entries"]
        self.assertEqual(len(entries), 2)
        merged = [e for e in entries if e["scope"] == "auth"][0]
        self.assertEqual(sorted(merged["shas"]), ["a", "b"])
        self.assertIn("feat(auth): A", merged["description"])
        self.assertIn("fix(auth): B", merged["description"])

    def test_seed_is_reproducible_and_varies(self):
        commits = [commit("2026-04-06", "a", ins=100), commit("2026-04-06", "b", ins=90),
                   commit("2026-04-06", "c", ins=80)]
        one = allocate.allocate(doc(commits, until="2026-04-06"), seed=7)
        two = allocate.allocate(doc(commits, until="2026-04-06"), seed=7)
        self.assertEqual(json.dumps(one), json.dumps(two))
        default_a = allocate.allocate(doc(commits, until="2026-04-06"))
        default_b = allocate.allocate(doc(commits, until="2026-04-06"))
        self.assertEqual(default_a["seed"], default_b["seed"])
        splits = {tuple(sorted(e["total"] for e in
                               allocate.allocate(doc(commits, until="2026-04-06"), seed=s)
                               ["weeks"][0]["entries"]))
                  for s in range(20)}
        self.assertGreater(len(splits), 1)

    def test_empty_days_are_filled_by_continuing_the_largest_entry(self):
        commits = [commit("2026-04-06", "big", ins=900, desc="feat: big"),
                   commit("2026-04-06", "small", ins=10, desc="fix: small")]
        r = allocate.allocate(doc(commits))
        week = r["weeks"][0]
        for d in week["days"][:5]:
            self.assertEqual(d["minutes"], 480)
        big = [e for e in week["entries"] if e["description"] == "feat: big"][0]
        self.assertGreaterEqual(len(big["minutes"]), 4)
        self.assertEqual(week["needs_input"], [])

    def test_overloaded_day_donates_whole_entries_to_empty_days(self):
        commits = [commit("2026-04-06", "t%d" % i, ins=10 + i) for i in range(10)]
        r = allocate.allocate(doc(commits, until="2026-04-07"))
        days = days_by_date(r)
        self.assertEqual(days["2026-04-07"]["minutes"], 480)
        per_day = {}
        for e in r["weeks"][0]["entries"]:
            for k in e["minutes"]:
                per_day[k] = per_day.get(k, 0) + 1
        self.assertEqual(per_day, {"2026-04-06": 9, "2026-04-07": 1})
        # 9 x 1:00 does not fit in 8h, so the minimum drops to 0:45 (no merging)
        mins = [e["minutes"]["2026-04-06"] for e in r["weeks"][0]["entries"]
                if "2026-04-06" in e["minutes"]]
        self.assertGreaterEqual(min(mins), 45)
        self.assertEqual(r["warnings"], [])

    def test_week_without_commits_needs_input(self):
        r = allocate.allocate(doc([commit("2026-04-06", "a")], until="2026-04-19"))
        self.assertEqual(r["weeks"][1]["needs_input"],
                         ["2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17"])
        self.assertEqual(r["weeks"][1]["total"], 0)

    def test_full_pto_week_needs_nothing(self):
        offs = allocate.parse_day_off("2026-04-06..2026-04-10:pto")
        r = allocate.allocate(doc([]), days_off=offs)
        self.assertEqual(r["needs_input"], [])
        self.assertEqual(r["total_minutes"], 0)

    def test_overtime_only_when_allowed(self):
        commits = [commit("2026-04-06", "t%d" % i) for i in range(10)]
        strict = allocate.allocate(doc(commits, until="2026-04-06"))
        self.assertEqual(days_by_date(strict)["2026-04-06"]["minutes"], 480)
        ot = allocate.allocate(doc(commits, until="2026-04-06"), allow_overtime=True,
                               max_hours_per_day=10)
        day = days_by_date(ot)["2026-04-06"]
        self.assertEqual(day["minutes"], 600)
        self.assertTrue(day.get("overtime"))

    def test_too_many_entries_get_merged(self):
        commits = [commit("2026-04-06", "t%02d" % i) for i in range(40)]
        r = allocate.allocate(doc(commits, until="2026-04-06"))
        entries = r["weeks"][0]["entries"]
        self.assertLessEqual(len(entries), 32)
        self.assertEqual(sum(e["total"] for e in entries), 480)
        self.assertTrue(r["warnings"])

    def test_increment_and_hours_validation(self):
        r = allocate.allocate(doc([commit("2026-04-06", "a"), commit("2026-04-06", "b", ins=50)],
                                  until="2026-04-06"), hours_per_day=7.5, increment=30)
        self.assertTrue(all(m % 30 == 0 for e in r["weeks"][0]["entries"]
                            for m in e["minutes"].values()))
        self.assertEqual(r["total_minutes"], 450)
        with self.assertRaises(ValueError):
            allocate.allocate(doc([]), hours_per_day=7.5, increment=60)

    def test_project_mapping(self):
        mapping = {"app": {"default": "My App", "scopes": {"auth": "My App - Auth"}}}
        commits = [commit("2026-04-06", "a", scope="auth"), commit("2026-04-06", "b"),
                   commit("2026-04-06", "c", repo="lib")]
        r = allocate.allocate(doc(commits, until="2026-04-06"), mapping=mapping)
        projects = {e["shas"][0]: e["project"] for e in r["weeks"][0]["entries"]}
        self.assertEqual(projects, {"a": "My App - Auth", "b": "My App", "c": None})

    def test_range_across_new_year_uses_both_years(self):
        r = allocate.allocate(doc([commit("2026-12-28", "a")], since="2026-12-21",
                                  until="2027-01-08"), country="PL")
        days = days_by_date(r)
        for iso in ("2026-12-24", "2026-12-25", "2027-01-01", "2027-01-06"):
            self.assertEqual(days[iso]["status"], "holiday", iso)

    def test_partial_weeks_mark_outside_days(self):
        r = allocate.allocate(doc([commit("2026-04-01", "a")], since="2026-04-01",
                                  until="2026-04-15"))
        days = days_by_date(r)
        self.assertEqual(days["2026-03-30"]["status"], "outside")
        self.assertEqual(days["2026-04-16"]["status"], "outside")
        self.assertEqual(len(r["weeks"]), 3)


class CliTest(unittest.TestCase):
    def test_profile_settings_and_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpath, ppath = os.path.join(tmp, "c.json"), os.path.join(tmp, "p.json")
            with open(cpath, "w") as f:
                json.dump(doc([commit("2026-04-06", "a", scope="auth")], until="2026-04-06"), f)
            with open(ppath, "w") as f:
                json.dump({"settings": {"hoursPerDay": 6, "timeIncrement": 30, "country": "other"},
                           "projectMapping": {"app": {"default": "App"}}}, f)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = allocate.main(["--commits", cpath, "--profile", ppath, "--member", "Jane"])
            self.assertEqual(code, 0)
            r = json.loads(out.getvalue())
            self.assertEqual(r["total_minutes"], 360)
            self.assertIsNone(r["country"])
            self.assertEqual(r["weeks"][0]["entries"][0]["project"], "App")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = allocate.main(["--commits", cpath, "--day-off", "2026-04-06:holiday"])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
