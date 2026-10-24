"""Shared test helpers: import path for the skill scripts and a git fixture repo."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "plugins", "git-timesheet", "skills", "timesheet")
SCRIPTS = os.path.join(SKILL_DIR, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def git_env(home):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"HOME": home, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "LC_ALL": "C"})
    return env


class FixtureRepo:
    """A throw-away git repo with explicit author/committer dates."""

    def __init__(self, path, home):
        self.path = path
        self.env = git_env(home)
        os.makedirs(path, exist_ok=True)
        self.git("init", "-q")
        self.git("checkout", "-q", "-b", "main")

    def git(self, *args, env=None):
        e = dict(self.env)
        e.update(env or {})
        r = subprocess.run(["git", "-C", self.path] + list(args), env=e,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode())
        return r.stdout.decode()

    def _dates(self, author, email, adate, cdate):
        return {"GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": email,
                "GIT_COMMITTER_NAME": "Committer", "GIT_COMMITTER_EMAIL": "c@example.com",
                "GIT_AUTHOR_DATE": adate, "GIT_COMMITTER_DATE": cdate or adate}

    def commit(self, message, files=None, adate="2026-04-01T10:00:00+00:00", cdate=None,
               author="Jane Doe", email="jane@example.com", allow_empty=False):
        for name, content in (files or {}).items():
            full = os.path.join(self.path, name)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(content)
            self.git("add", name)
        args = ["commit", "-q", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        self.git(*args, env=self._dates(author, email, adate, cdate))
        return self.git("rev-parse", "HEAD").strip()

    def merge(self, branch, message, adate, author="Jane Doe", email="jane@example.com"):
        self.git("merge", "-q", "--no-ff", branch, "-m", message,
                 env=self._dates(author, email, adate, None))
        return self.git("rev-parse", "HEAD").strip()


def lines(n, prefix="line"):
    return "".join("%s %d\n" % (prefix, i) for i in range(n))
