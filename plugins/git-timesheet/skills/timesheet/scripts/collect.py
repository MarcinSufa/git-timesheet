#!/usr/bin/env python3
"""Collect commits from one or more git repos as JSON.

Usage:
    python3 collect.py --since 2026-04-01 --until 2026-04-15 \\
        --author "janedoe" --author "jane@example.com" \\
        --repo /path/to/my-app=my-app --repo /path/to/shared-lib \\
        [--all] [--merges] [--regex] [--case-sensitive]
    python3 collect.py --list-authors --since ... --until ... --repo ...

Dates are inclusive and compared with the commit's AUTHOR date in the
author's own time zone, which is the date the timesheet shows. Git's own
--since/--until filter by committer date, so they are only used as a wide
lower bound and the exact filter happens here.

Author patterns are fixed strings matched case-insensitively against the
author name and email (any pattern matches). Use --regex for git regular
expressions and --case-sensitive to turn off case folding.

Output (stdout):
    {"since": ..., "until": ..., "authors": [...],
     "repos": [{"label", "path", "count", "latest", "error"}],
     "commits": [{"repo", "sha", "author_date", "date", "author", "email",
                  "subject", "description", "scope", "insertions",
                  "deletions", "files", "merge"}]}

Commits without a diff (empty commits, merges) have files = 0. Merge commits
are skipped unless --merges is given; their diff is not counted, so a merged
branch is never counted twice. A commit reachable from several listed repos
(forks, clones) is reported once.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

RS, US = "\x1e", "\x1f"
FORMAT = "%x1e%H%x1f%aI%x1f%P%x1f%aN%x1f%aE%x1f%s"
SLACK_DAYS = 2  # time-zone slack for the committer-date lower bound

CONVENTIONAL = re.compile(r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]+)\))?!?:\s*(?P<rest>.*)$")


def parse_iso_date(s):
    return dt.date.fromisoformat(s)


def scope_of(subject):
    m = CONVENTIONAL.match(subject.strip())
    return m.group("scope").strip() if m and m.group("scope") else None


def clean_subject(subject, max_len=80):
    """Turn a commit subject into a timesheet task description.

    - drop PR numbers "(#2505)"
    - move "Refs: PROJ-123" to a trailing "(PROJ-123)" (once)
    - drop a trailing GitHub truncation ellipsis
    - capitalise the first word after "type(scope):"
    - truncate to max_len characters with "..."
    """
    s = " ".join(subject.split())
    s = re.sub(r"\s*\(#\d+\)", "", s)
    tickets = re.findall(r"\s*\bRefs?:\s*([A-Z][A-Z0-9]+-\d+)", s)
    s = re.sub(r"\s*\bRefs?:\s*[A-Z][A-Z0-9]+-\d+", "", s)
    s = re.sub(r"\s*(…|\.\.\.)$", "", s).rstrip()
    for t in tickets:
        if t not in s:
            s = "%s (%s)" % (s, t)
    m = CONVENTIONAL.match(s)
    if m and m.group("rest"):
        rest = m.group("rest")
        head = s[: len(s) - len(rest)]
        s = head + rest[0].upper() + rest[1:]
    elif s:
        s = s[0].upper() + s[1:]
    if len(s) > max_len:
        s = s[: max_len - 3].rstrip() + "..."
    return s


def _git(repo, args):
    cmd = ["git", "-C", repo, "-c", "log.showSignature=false", "-c", "core.quotepath=off"] + args
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip() or "git failed")
    return r.stdout.decode("utf-8", "replace")


def _log_args(since, authors, all_refs, merges, regex, case_sensitive):
    lower = since - dt.timedelta(days=SLACK_DAYS)
    args = ["log", "--no-color", "--since=%s 00:00:00" % lower.isoformat()]
    if all_refs:
        args.append("--all")
    if not merges:
        args.append("--no-merges")
    if not regex:
        args.append("--fixed-strings")
    if not case_sensitive:
        args.append("--regexp-ignore-case")
    args += ["--author=%s" % a for a in authors]
    return args


def parse_log(text):
    """Parse `git log --format=FORMAT --numstat` output into dicts."""
    commits = []
    for record in text.split(RS):
        if not record.strip():
            continue
        lines = record.split("\n")
        fields = lines[0].split(US)
        if len(fields) != 6:
            raise ValueError("unexpected git log record: %r" % lines[0][:200])
        sha, adate, parents, name, email, subject = fields
        ins = dels = files = 0
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            a, d, _path = parts
            files += 1
            ins += int(a) if a.isdigit() else 0  # "-" for binary files
            dels += int(d) if d.isdigit() else 0
        commits.append({
            "sha": sha,
            "author_date": adate,
            "date": adate[:10],
            "author": name,
            "email": email,
            "subject": subject,
            "insertions": ins,
            "deletions": dels,
            "files": files,
            "merge": len(parents.split()) > 1,
        })
    return commits


def parse_repo_arg(value):
    """'/path/to/repo=label' or '/path/to/repo' (label = directory name)."""
    if "=" in value:
        path, label = value.rsplit("=", 1)
    else:
        path, label = value, ""
    path = os.path.expanduser(path)
    return path, label or os.path.basename(os.path.normpath(path))


def collect(repos, authors, since, until, all_refs=False, merges=False,
            regex=False, case_sensitive=False):
    out = {"since": since.isoformat(), "until": until.isoformat(),
           "authors": list(authors), "repos": [], "commits": []}
    seen = set()
    args = _log_args(since, authors, all_refs, merges, regex, case_sensitive)
    args += ["--format=" + FORMAT, "--numstat"]
    for path, label in repos:
        info = {"label": label, "path": path, "count": 0, "latest": None, "error": None}
        out["repos"].append(info)
        if not os.path.isdir(path):
            info["error"] = "not found on disk"
            continue
        try:
            commits = parse_log(_git(path, args))
        except (RuntimeError, ValueError) as e:
            info["error"] = str(e)
            continue
        for c in commits:
            if not (since.isoformat() <= c["date"] <= until.isoformat()):
                continue
            if c["sha"] in seen:
                continue
            seen.add(c["sha"])
            c["repo"] = label
            c["scope"] = scope_of(c["subject"])
            c["description"] = clean_subject(c["subject"])
            out["commits"].append(c)
            info["count"] += 1
            if info["latest"] is None or c["date"] > info["latest"]:
                info["latest"] = c["date"]
    out["commits"].sort(key=lambda c: (c["date"], c["author_date"], c["repo"]))
    return out


def list_authors(repos, since, until, all_refs=False):
    """Every author (name <email>) with commits in the range, per repo."""
    out = {}
    lower = since - dt.timedelta(days=SLACK_DAYS)
    for path, label in repos:
        if not os.path.isdir(path):
            out[label] = {"error": "not found on disk"}
            continue
        args = ["log", "--no-color", "--since=%s 00:00:00" % lower.isoformat(),
                "--format=%aI%x1f%aN <%aE>"]
        if all_refs:
            args.append("--all")
        try:
            text = _git(path, args)
        except RuntimeError as e:
            out[label] = {"error": str(e)}
            continue
        names = set()
        for line in text.splitlines():
            if US not in line:
                continue
            adate, who = line.split(US, 1)
            if since.isoformat() <= adate[:10] <= until.isoformat():
                names.add(who)
        out[label] = sorted(names)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Collect git commits as JSON")
    p.add_argument("--repo", action="append", required=True,
                   help="repo path, optionally PATH=LABEL (repeatable)")
    p.add_argument("--author", action="append", default=[],
                   help="author name/email pattern (repeatable, any matches)")
    p.add_argument("--since", required=True, type=parse_iso_date, help="YYYY-MM-DD, inclusive")
    p.add_argument("--until", required=True, type=parse_iso_date, help="YYYY-MM-DD, inclusive")
    p.add_argument("--all", action="store_true", help="scan all refs, not only HEAD")
    p.add_argument("--merges", action="store_true", help="include merge commits")
    p.add_argument("--regex", action="store_true", help="author patterns are regexes")
    p.add_argument("--case-sensitive", action="store_true")
    p.add_argument("--list-authors", action="store_true",
                   help="list every author in the range instead (debug missing commits)")
    a = p.parse_args(argv)
    if a.until < a.since:
        p.error("--until is before --since")
    repos = [parse_repo_arg(r) for r in a.repo]
    if a.list_authors:
        print(json.dumps(list_authors(repos, a.since, a.until, a.all), indent=2, ensure_ascii=False))
        return 0
    if not a.author:
        p.error("at least one --author is required")
    result = collect(repos, a.author, a.since, a.until, a.all, a.merges, a.regex, a.case_sensitive)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    for r in result["repos"]:
        if r["error"]:
            print("WARNING: skipped %s (%s): %s" % (r["label"], r["path"], r["error"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
