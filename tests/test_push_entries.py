import contextlib
import io
import json
import os
import tempfile
import unittest

import helpers  # noqa: F401
import allocate
import push_entries


def alloc():
    commits = [{"date": "2026-03-03", "sha": s, "insertions": ins, "deletions": 0, "files": 1,
                "scope": None, "repo": "app", "description": "task " + s}
               for s, ins in (("a", 400), ("b", 30))]
    return allocate.allocate({"since": "2026-03-03", "until": "2026-03-03", "commits": commits},
                             seed=3, mapping={"app": {"default": "App"}})


class PushEntriesTest(unittest.TestCase):
    def test_back_to_back_with_lunch_and_offsets(self):
        tz = push_entries._offset("+01:00")
        out = push_entries.entries(alloc(), tz=tz)
        self.assertEqual(len(out), 2)
        self.assertEqual(sum(e["minutes"] for e in out), 480)
        first, second = out
        self.assertEqual(first["start_local"], "2026-03-03T09:00:00")
        self.assertEqual(first["start"], "2026-03-03T09:00:00+01:00")
        self.assertEqual(first["start_utc"], "2026-03-03T08:00:00Z")
        self.assertEqual(second["end_local"], "2026-03-03T18:00:00")  # 8h + 1h lunch
        self.assertEqual(first["seconds"], first["minutes"] * 60)
        self.assertEqual(first["project"], "App")
        self.assertEqual(first["hours"], round(first["minutes"] / 60.0, 2))

    def test_cli_no_lunch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.json")
            with open(path, "w") as f:
                json.dump(alloc(), f)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = push_entries.main(["--allocation", path, "--lunch", "none",
                                          "--day-start", "08:00", "--tz-offset=-05:00"])
            self.assertEqual(code, 0)
            out = json.loads(buf.getvalue())
            self.assertEqual(out[-1]["end"], "2026-03-03T16:00:00-05:00")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(push_entries.main(["--allocation", path, "--tz-offset", "CET"]), 2)

    def test_payloads(self):
        out = push_entries.entries(alloc(), tz=push_entries._offset("+01:00"))
        e = out[0]
        ids = {"App": 77}
        self.assertEqual(push_entries.payload("toggl", e, "123", ids),
                         {"description": e["description"], "start": "2026-03-03T09:00:00+01:00",
                          "duration": e["seconds"], "workspace_id": 123, "project_id": 77,
                          "created_with": "git-timesheet"})
        self.assertEqual(push_entries.payload("clockify", e, ids=ids)["start"], "2026-03-03T08:00:00Z")
        self.assertEqual(push_entries.payload("tmetric", e)["projectId"], None)
        h = push_entries.payload("harvest", e, ids={"App": {"project_id": 1, "task_id": 2}})
        self.assertEqual((h["project_id"], h["task_id"], h["spent_date"], h["hours"]),
                         (1, 2, "2026-03-03", e["hours"]))

    def test_cli_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.json")
            with open(path, "w") as f:
                json.dump(alloc(), f)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = push_entries.main(["--allocation", path, "--service", "clockify"])
            self.assertEqual(code, 0)
            self.assertIn("payload", json.loads(buf.getvalue())[0])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                push_entries.main(["--allocation", path, "--service", "toggl"])


if __name__ == "__main__":
    unittest.main()
