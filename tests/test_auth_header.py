import base64
import os
import stat
import subprocess
import sys
import tempfile
import unittest

import helpers
import auth_header

SCRIPT = os.path.join(helpers.SCRIPTS, "auth_header.py")
SECRET = "tok_SECRET_1234567890"


def run(args, env):
    full = {"PATH": os.environ.get("PATH", ""), "TMPDIR": env.pop("TMPDIR", tempfile.gettempdir())}
    full.update(env)
    return subprocess.run([sys.executable, SCRIPT] + args, env=full,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


class AuthHeaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_header_shapes(self):
        env = {"GIT_TIMESHEET_TOGGL_TOKEN": "abc", "GIT_TIMESHEET_CLOCKIFY_TOKEN": "c",
               "GIT_TIMESHEET_TMETRIC_TOKEN": "t", "GIT_TIMESHEET_HARVEST_TOKEN": "h",
               "GIT_TIMESHEET_HARVEST_ACCOUNT_ID": "42"}
        self.assertEqual(auth_header.header_lines("toggl", env),
                         ["Authorization: Basic " + base64.b64encode(b"abc:api_token").decode()])
        self.assertEqual(auth_header.header_lines("clockify", env), ["X-Api-Key: c"])
        self.assertEqual(auth_header.header_lines("tmetric", env), ["Authorization: Bearer t"])
        self.assertEqual(auth_header.header_lines("harvest", env)[:2],
                         ["Authorization: Bearer h", "Harvest-Account-Id: 42"])

    def test_file_is_private_and_token_never_printed(self):
        r = run(["clockify"], {"GIT_TIMESHEET_CLOCKIFY_TOKEN": SECRET, "TMPDIR": self.tmp.name})
        self.assertEqual(r.returncode, 0, r.stderr)
        path = r.stdout.strip()
        self.assertTrue(path.startswith(self.tmp.name))
        self.assertNotIn(SECRET[:4], r.stdout + r.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with open(path) as f:
            self.assertEqual(f.read(), "X-Api-Key: %s\n" % SECRET)

    def test_out_path_is_forced_private(self):
        out = os.path.join(self.tmp.name, "h")
        with open(out, "w"):
            pass
        os.chmod(out, 0o644)
        r = run(["tmetric", "--out", out], {"GIT_TIMESHEET_TMETRIC_TOKEN": SECRET})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)

    def test_check_and_missing(self):
        r = run(["harvest", "--check"], {"GIT_TIMESHEET_HARVEST_TOKEN": SECRET})
        self.assertEqual((r.returncode, r.stdout.strip()),
                         (1, "missing: GIT_TIMESHEET_HARVEST_ACCOUNT_ID"))
        r = run(["harvest"], {"GIT_TIMESHEET_HARVEST_TOKEN": SECRET})
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertNotIn(SECRET[:4], r.stderr)
        r = run(["toggl", "--check"], {"GIT_TIMESHEET_TOGGL_TOKEN": SECRET})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "set"))

    def test_line_break_in_token_is_rejected(self):
        r = run(["clockify", "--out", os.path.join(self.tmp.name, "h")],
                {"GIT_TIMESHEET_CLOCKIFY_TOKEN": "a\nX-Evil: 1"})
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "h")))


if __name__ == "__main__":
    unittest.main()
