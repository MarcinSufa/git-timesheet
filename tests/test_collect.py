import contextlib
import datetime as dt
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import helpers
import collect

D = dt.date


class CleanSubjectTest(unittest.TestCase):
    def test_pr_number_and_refs(self):
        self.assertEqual(collect.clean_subject("fix(order): clear payments (#2505) Refs: PROJ-8450"),
                         "fix(order): Clear payments (PROJ-8450)")

    def test_ticket_already_present_is_not_repeated(self):
        self.assertEqual(collect.clean_subject("feat: PROJ-1 add x Refs: PROJ-1"),
                         "feat: PROJ-1 add x")

    def test_truncation_and_ellipsis(self):
        self.assertEqual(collect.clean_subject("fix: prevent freeze after consecutive Save &…"),
                         "fix: Prevent freeze after consecutive Save &")
        long = "feat(api): " + "x" * 100
        out = collect.clean_subject(long)
        self.assertEqual(len(out), 80)
        self.assertTrue(out.endswith("..."))

    def test_scope(self):
        self.assertEqual(collect.scope_of("feat(auth): add"), "auth")
        self.assertEqual(collect.scope_of("feat(auth)!: add"), "auth")
        self.assertIsNone(collect.scope_of("feat: add"))
        self.assertIsNone(collect.scope_of("Merge branch 'x'"))


class ParseLogTest(unittest.TestCase):
    def test_empty_commits_and_binary_files_do_not_shift_stats(self):
        RS, US = collect.RS, collect.US
        text = (
            RS + US.join(["a" * 40, "2026-04-01T10:00:00+02:00", "p1", "Jane", "j@x", "first"]) + "\n\n"
            "3\t1\tsrc/a.py\n-\t-\timg.png\n"
            + RS + US.join(["b" * 40, "2026-04-02T10:00:00+02:00", "p1", "Jane", "j@x", "empty"]) + "\n"
            + RS + US.join(["c" * 40, "2026-04-03T10:00:00+02:00", "p1 p2", "Jane", "j@x", "merge"]) + "\n"
            + RS + US.join(["d" * 40, "2026-04-04T10:00:00+02:00", "p1", "Jane", "j@x", "last"]) + "\n\n"
            "10\t0\tb.txt\n"
        )
        commits = collect.parse_log(text)
        self.assertEqual([(c["subject"], c["files"], c["insertions"], c["deletions"], c["merge"])
                          for c in commits],
                         [("first", 2, 3, 1, False), ("empty", 0, 0, 0, False),
                          ("merge", 0, 0, 0, True), ("last", 1, 10, 0, False)])

    def test_subject_with_pipes_and_tabs(self):
        RS, US = collect.RS, collect.US
        text = RS + US.join(["a" * 40, "2026-04-01T10:00:00Z", "", "J", "j@x",
                             "fix: a | b\tc"]) + "\n"
        self.assertEqual(collect.parse_log(text)[0]["subject"], "fix: a | b\tc")


class CollectRepoTest(unittest.TestCase):
    """Fixture repo with an empty commit, a merge commit and odd dates."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = mock.patch.dict(os.environ, helpers.git_env(cls.tmp.name), clear=True)
        cls.env.start()
        r = cls.repo = helpers.FixtureRepo(os.path.join(cls.tmp.name, "app"), cls.tmp.name)
        cls.sha = {}
        cls.sha["feat"] = r.commit("feat(auth): add login (#12)", {"a.py": helpers.lines(30)},
                                   adate="2026-04-01T09:00:00+02:00")
        cls.sha["empty"] = r.commit("chore: empty marker", allow_empty=True,
                                    adate="2026-04-02T09:00:00+02:00")
        r.git("checkout", "-q", "-b", "feature")
        cls.sha["branch"] = r.commit("fix(ui): button", {"b.css": helpers.lines(5)},
                                     adate="2026-04-02T12:00:00+02:00")
        r.git("checkout", "-q", "main")
        cls.sha["docs"] = r.commit("docs: readme", {"README.md": helpers.lines(3), "c.txt": "x\n"},
                                   adate="2026-04-03T10:00:00+02:00")
        cls.sha["merge"] = r.merge("feature", "Merge branch 'feature'", "2026-04-03T15:00:00+02:00")
        # authored in range, rebased (committed) after the range
        cls.sha["rebased"] = r.commit("refactor: tidy", {"d.py": helpers.lines(2)},
                                      adate="2026-04-06T23:30:00-07:00",
                                      cdate="2026-04-20T08:00:00+00:00")
        # authored before the range, committed (cherry-picked) inside it
        cls.sha["old"] = r.commit("fix: old work", {"e.py": "1\n"},
                                  adate="2026-03-20T10:00:00+00:00",
                                  cdate="2026-04-02T10:00:00+00:00")
        cls.sha["other"] = r.commit("feat: someone else", {"f.py": "1\n"},
                                    adate="2026-04-02T10:00:00+00:00",
                                    author="Bob", email="bob@example.com")
        r.git("checkout", "-q", "-b", "side")
        cls.sha["side"] = r.commit("feat: side branch only", {"g.py": "1\n"},
                                   adate="2026-04-03T10:00:00+00:00")
        r.git("checkout", "-q", "main")
        cls.repos = [(r.path, "app")]

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.tmp.cleanup()

    def run_collect(self, **kw):
        args = dict(repos=self.repos, authors=["jane"], since=D(2026, 4, 1), until=D(2026, 4, 7))
        args.update(kw)
        return collect.collect(**args)

    def test_stats_stay_aligned_with_empty_and_merge_commits(self):
        out = self.run_collect()
        got = {c["sha"]: c for c in out["commits"]}
        self.assertEqual((got[self.sha["feat"]]["files"], got[self.sha["feat"]]["insertions"]), (1, 30))
        self.assertEqual(got[self.sha["empty"]]["files"], 0)
        self.assertEqual((got[self.sha["docs"]]["files"], got[self.sha["docs"]]["insertions"]), (2, 4))
        self.assertEqual((got[self.sha["branch"]]["files"], got[self.sha["branch"]]["insertions"]), (1, 5))
        self.assertEqual(got[self.sha["feat"]]["description"], "feat(auth): Add login")
        self.assertEqual(got[self.sha["feat"]]["scope"], "auth")

    def test_merges_skipped_by_default_and_opt_in(self):
        self.assertNotIn(self.sha["merge"], [c["sha"] for c in self.run_collect()["commits"]])
        merged = {c["sha"]: c for c in self.run_collect(merges=True)["commits"]}
        self.assertTrue(merged[self.sha["merge"]]["merge"])
        self.assertEqual(merged[self.sha["merge"]]["files"], 0)  # not double-counted

    def test_author_date_filter(self):
        shas = [c["sha"] for c in self.run_collect()["commits"]]
        self.assertIn(self.sha["rebased"], shas)  # committer date after the range
        self.assertNotIn(self.sha["old"], shas)  # author date before the range
        rebased = [c for c in self.run_collect()["commits"] if c["sha"] == self.sha["rebased"]][0]
        self.assertEqual(rebased["date"], "2026-04-06")  # author's local date, as printed
        early = self.run_collect(since=D(2026, 3, 20), until=D(2026, 3, 20))
        self.assertEqual([c["sha"] for c in early["commits"]], [self.sha["old"]])

    def test_author_patterns(self):
        self.assertNotIn(self.sha["other"], [c["sha"] for c in self.run_collect()["commits"]])
        both = self.run_collect(authors=["JANE", "bob@example.com"])
        self.assertIn(self.sha["other"], [c["sha"] for c in both["commits"]])
        self.assertEqual(self.run_collect(authors=["JANE"], case_sensitive=True)["commits"], [])

    def test_all_refs(self):
        self.assertNotIn(self.sha["side"], [c["sha"] for c in self.run_collect()["commits"]])
        self.assertIn(self.sha["side"], [c["sha"] for c in self.run_collect(all_refs=True)["commits"]])

    def test_repo_summary_and_missing_repo(self):
        out = self.run_collect(repos=self.repos + [("/nonexistent/repo", "gone"),
                                                   (self.repos[0][0], "dup")])
        info = {r["label"]: r for r in out["repos"]}
        self.assertEqual(info["app"]["count"], len(out["commits"]))
        self.assertEqual(info["app"]["latest"], "2026-04-06")
        self.assertEqual(info["gone"]["error"], "not found on disk")
        self.assertEqual(info["dup"]["count"], 0)  # same commits are not counted twice

    def test_list_authors(self):
        out = collect.list_authors(self.repos, D(2026, 4, 1), D(2026, 4, 7))
        self.assertEqual(out["app"], ["Bob <bob@example.com>", "Jane Doe <jane@example.com>"])

    def test_cli(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = collect.main(["--repo", self.repos[0][0] + "=app", "--author", "jane",
                                 "--since", "2026-04-01", "--until", "2026-04-07"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["repos"][0]["label"], "app")

    def test_old_shortstat_pipeline_was_broken(self):
        """Documents the bug this script replaces (SKILL.md <= 1.0.4)."""
        r = subprocess.run("git -C '%s' log --format='%%ad | %%s' --date=short --shortstat "
                           "--since=2026-04-01 | paste - - -" % self.repos[0][0],
                           shell=True, stdout=subprocess.PIPE, env=os.environ)
        rows = r.stdout.decode().splitlines()
        self.assertTrue(any(row.count("|") > 1 for row in rows))  # two commits on one line


if __name__ == "__main__":
    unittest.main()
