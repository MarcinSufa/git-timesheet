import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import helpers  # noqa: F401
import datadir


class ResolveTest(unittest.TestCase):
    def test_order(self):
        env = {"GIT_TIMESHEET_HOME": "/a", "CLAUDE_PLUGIN_DATA": "/b", "XDG_CONFIG_HOME": "/c"}
        self.assertEqual(datadir.resolve("/p", env), ("/a", "GIT_TIMESHEET_HOME"))
        del env["GIT_TIMESHEET_HOME"]
        self.assertEqual(datadir.resolve("/p", env), ("/p", "CLAUDE_PLUGIN_DATA"))
        self.assertEqual(datadir.resolve(None, env), ("/b", "CLAUDE_PLUGIN_DATA"))
        del env["CLAUDE_PLUGIN_DATA"]
        self.assertEqual(datadir.resolve(None, env), ("/c/git-timesheet", "XDG_CONFIG_HOME"))

    def test_unsubstituted_variable_is_ignored(self):
        env = {"XDG_CONFIG_HOME": "/c"}
        self.assertEqual(datadir.resolve("${CLAUDE_PLUGIN_DATA}", env)[0], "/c/git-timesheet")
        self.assertEqual(datadir.resolve("", env)[0], "/c/git-timesheet")

    def test_home_fallback(self):
        with mock.patch.dict(os.environ, {"HOME": "/home/x"}, clear=True):
            self.assertEqual(datadir.resolve(None, {})[0], "/home/x/.config/git-timesheet")


class LegacyTest(unittest.TestCase):
    def test_detect_and_migrate_without_overwriting(self):
        with tempfile.TemporaryDirectory() as home:
            legacy = os.path.join(home, ".claude", "skills", "timesheet")
            os.makedirs(os.path.join(legacy, "profiles"))
            os.makedirs(os.path.join(legacy, "templates"))
            for rel, text in (("profiles/acme.json", "{}"), ("profiles/mine.json", '{"old": 1}'),
                              ("templates/brand.html", "x")):
                with open(os.path.join(legacy, rel), "w") as f:
                    f.write(text)
            target = os.path.join(home, "data")
            os.makedirs(os.path.join(target, "profiles"))
            with open(os.path.join(target, "profiles", "mine.json"), "w") as f:
                f.write('{"new": 1}')
            env = {"HOME": home, "CLAUDE_PLUGIN_DATA": target}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(datadir.legacy_dir(target), legacy)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(datadir.main(["--migrate"]), 0)
                out = json.loads(buf.getvalue())
            self.assertEqual(out["source"], "CLAUDE_PLUGIN_DATA")
            self.assertEqual(out["profiles"], ["acme", "mine"])
            self.assertEqual(out["templates"], ["brand"])
            self.assertEqual(len(out["migrated"]), 2)
            with open(os.path.join(target, "profiles", "mine.json")) as f:
                self.assertEqual(f.read(), '{"new": 1}')

    def test_no_legacy(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"HOME": home}, clear=True):
                self.assertIsNone(datadir.legacy_dir(os.path.join(home, "d")))


if __name__ == "__main__":
    unittest.main()
