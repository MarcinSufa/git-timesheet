#!/usr/bin/env python3
"""Write time-tracker auth headers to a private file for `curl -H @file`.

Usage:
    python3 auth_header.py --check toggl          # prints "set" or what is missing
    HDR=$(python3 auth_header.py toggl)           # prints only the file path
    curl -sS -H @"$HDR" -H "Content-Type: application/json" ...
    rm -f "$HDR"

Tokens are read from the environment only and never printed:
    toggl     GIT_TIMESHEET_TOGGL_TOKEN
    clockify  GIT_TIMESHEET_CLOCKIFY_TOKEN
    tmetric   GIT_TIMESHEET_TMETRIC_TOKEN
    harvest   GIT_TIMESHEET_HARVEST_TOKEN + GIT_TIMESHEET_HARVEST_ACCOUNT_ID

The header file is created with mode 0600 (default: a new file in $TMPDIR);
delete it after the push. Keeping the token out of curl's argv keeps it out
of `ps` output and shell history.
"""
import argparse
import base64
import os
import sys
import tempfile

ENV = {
    "toggl": ["GIT_TIMESHEET_TOGGL_TOKEN"],
    "clockify": ["GIT_TIMESHEET_CLOCKIFY_TOKEN"],
    "tmetric": ["GIT_TIMESHEET_TMETRIC_TOKEN"],
    "harvest": ["GIT_TIMESHEET_HARVEST_TOKEN", "GIT_TIMESHEET_HARVEST_ACCOUNT_ID"],
}


def missing(service, env=None):
    env = os.environ if env is None else env
    return [v for v in ENV[service] if not env.get(v, "").strip()]


def _value(env, name):
    value = env[name].strip()
    if "\n" in value or "\r" in value:
        raise ValueError("%s contains a line break" % name)
    return value


def header_lines(service, env=None):
    env = os.environ if env is None else env
    if service == "toggl":
        raw = "%s:api_token" % _value(env, "GIT_TIMESHEET_TOGGL_TOKEN")
        return ["Authorization: Basic " + base64.b64encode(raw.encode()).decode()]
    if service == "clockify":
        return ["X-Api-Key: " + _value(env, "GIT_TIMESHEET_CLOCKIFY_TOKEN")]
    if service == "tmetric":
        return ["Authorization: Bearer " + _value(env, "GIT_TIMESHEET_TMETRIC_TOKEN")]
    if service == "harvest":
        return ["Authorization: Bearer " + _value(env, "GIT_TIMESHEET_HARVEST_TOKEN"),
                "Harvest-Account-Id: " + _value(env, "GIT_TIMESHEET_HARVEST_ACCOUNT_ID"),
                "User-Agent: git-timesheet"]
    raise ValueError(service)


def write_header_file(service, path=None, env=None):
    lines = header_lines(service, env)
    if path:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.chmod(path, 0o600)
    else:
        fd, path = tempfile.mkstemp(prefix="git-timesheet-%s-" % service, suffix=".hdr")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description="Auth header file for curl -H @file")
    p.add_argument("service", choices=sorted(ENV))
    p.add_argument("--check", action="store_true", help="only report whether the env vars are set")
    p.add_argument("--out", help="header file path (default: new temp file)")
    a = p.parse_args(argv)
    gone = missing(a.service)
    if a.check:
        print("set" if not gone else "missing: " + ", ".join(gone))
        return 0 if not gone else 1
    if gone:
        print("ERROR: set %s in your shell profile and restart Claude Code "
              "(never paste tokens into the chat)" % ", ".join(gone), file=sys.stderr)
        return 2
    try:
        print(write_header_file(a.service, a.out))
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
