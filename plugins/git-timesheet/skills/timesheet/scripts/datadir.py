#!/usr/bin/env python3
"""Where git-timesheet keeps profiles and templates.

Usage:
    python3 datadir.py --plugin-data "${CLAUDE_PLUGIN_DATA}" [--init] [--migrate]

Resolution order:
  1. $GIT_TIMESHEET_HOME
  2. the plugin's persistent data dir: --plugin-data or $CLAUDE_PLUGIN_DATA
     (set by Claude Code for plugins; survives plugin updates)
  3. ${XDG_CONFIG_HOME:-~/.config}/git-timesheet (skill installed by hand)

Versions up to 1.0.4 stored data in ~/.claude/skills/timesheet/. If that
folder still has profiles or templates, it is reported as "legacy" and
--migrate copies them (never overwriting) into the resolved directory.

Prints JSON: {"dir", "source", "profiles": [...], "templates": [...], "legacy"}.
"""
import argparse
import json
import os
import shutil
import sys

LEGACY = os.path.join("~", ".claude", "skills", "timesheet")


def _usable(value):
    # An unsubstituted "${CLAUDE_PLUGIN_DATA}" means we are not running as a plugin.
    return bool(value) and "${" not in value


def resolve(plugin_data=None, env=None):
    env = os.environ if env is None else env
    if _usable(env.get("GIT_TIMESHEET_HOME")):
        return os.path.expanduser(env["GIT_TIMESHEET_HOME"]), "GIT_TIMESHEET_HOME"
    for value in (plugin_data, env.get("CLAUDE_PLUGIN_DATA")):
        if _usable(value):
            return os.path.expanduser(value), "CLAUDE_PLUGIN_DATA"
    base = env.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "git-timesheet"), "XDG_CONFIG_HOME"


def _names(folder, ext):
    try:
        return sorted(f[: -len(ext)] for f in os.listdir(folder) if f.endswith(ext))
    except OSError:
        return []


def legacy_dir(resolved):
    legacy = os.path.expanduser(LEGACY)
    if os.path.realpath(legacy) == os.path.realpath(resolved):
        return None
    if _names(os.path.join(legacy, "profiles"), ".json") or \
            _names(os.path.join(legacy, "templates"), ".html"):
        return legacy
    return None


def migrate(legacy, target):
    copied = []
    for sub, ext in (("profiles", ".json"), ("templates", ".html")):
        src_dir, dst_dir = os.path.join(legacy, sub), os.path.join(target, sub)
        for name in _names(src_dir, ext):
            dst = os.path.join(dst_dir, name + ext)
            if os.path.exists(dst):
                continue
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(os.path.join(src_dir, name + ext), dst)
            copied.append(dst)
    return copied


def main(argv=None):
    p = argparse.ArgumentParser(description="Resolve the git-timesheet data directory")
    p.add_argument("--plugin-data", help='pass "${CLAUDE_PLUGIN_DATA}"')
    p.add_argument("--init", action="store_true", help="create profiles/ and templates/")
    p.add_argument("--migrate", action="store_true",
                   help="copy profiles/templates from the pre-1.1 location")
    a = p.parse_args(argv)
    d, source = resolve(a.plugin_data)
    out = {"dir": d, "source": source}
    if a.init or a.migrate:
        for sub in ("profiles", "templates"):
            os.makedirs(os.path.join(d, sub), exist_ok=True)
    legacy = legacy_dir(d)
    if a.migrate and legacy:
        out["migrated"] = migrate(legacy, d)
    out["profiles"] = _names(os.path.join(d, "profiles"), ".json")
    out["templates"] = _names(os.path.join(d, "templates"), ".html")
    out["legacy"] = legacy
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
