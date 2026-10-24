"""Static checks of SKILL.md and its references (no network, no Claude)."""
import os
import re
import unittest

import helpers

SKILL = os.path.join(helpers.SKILL_DIR, "SKILL.md")
REFS = os.path.join(helpers.SKILL_DIR, "references")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    return m.group(1)


class SkillMdTest(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)
        self.fm = frontmatter(self.text)

    def test_size(self):
        self.assertLess(len(self.text.encode("utf-8")), 12500)

    def test_frontmatter(self):
        self.assertIn("name: timesheet", self.fm)
        self.assertNotRegex(self.fm, r"(?m)^version:")
        self.assertRegex(self.fm, r'(?m)^argument-hint: "\[date range\] \[profile\]"$')
        desc = re.search(r"description: \|\n((?:  .*\n?)+)", self.fm).group(1)
        self.assertLessEqual(len(desc), 1024)
        for trigger in ("zrób timesheet", "rozliczenie godzin z commitów",
                        "raport godzin za tydzień", "generate timesheets"):
            self.assertIn(trigger, desc)

    def test_both_playwright_prefixes(self):
        self.assertIn("mcp__playwright__browser_run_code", self.fm)
        self.assertIn("mcp__plugin_playwright_playwright__browser_run_code", self.fm)
        pdf = read(os.path.join(REFS, "pdf.md"))
        self.assertIn("mcp__playwright__browser_", pdf)
        self.assertIn("mcp__plugin_playwright_playwright__browser_", pdf)

    def test_links_and_scripts_exist(self):
        docs = [SKILL] + [os.path.join(REFS, f) for f in os.listdir(REFS)]
        for doc in docs:
            text = read(doc)
            base = os.path.dirname(doc)
            for link in re.findall(r"\]\(([^)#]+\.md)\)", text):
                self.assertTrue(os.path.isfile(os.path.join(base, link)), (doc, link))
            for script in re.findall(r"scripts/(\w+\.py)", text) + \
                    re.findall(r'"\$S/(\w+\.py)"', text):
                self.assertTrue(os.path.isfile(os.path.join(helpers.SCRIPTS, script)),
                                (doc, script))
        for ref in re.findall(r"references/(\w+\.md)", self.text):
            self.assertTrue(os.path.isfile(os.path.join(REFS, ref)), ref)

    def test_no_heading_level_jumps(self):
        for doc in [SKILL] + [os.path.join(REFS, f) for f in os.listdir(REFS)]:
            text = re.sub(r"```.*?```", "", read(doc), flags=re.S)
            levels = [len(h) for h in re.findall(r"(?m)^(#+) ", text)]
            self.assertEqual(levels[0], 1, doc)
            self.assertEqual(levels.count(1), 1, doc)
            for a, b in zip(levels, levels[1:]):
                self.assertLessEqual(b - a, 1, doc)

    def test_no_secret_echo_or_home_paths(self):
        for doc in [SKILL] + [os.path.join(REFS, f) for f in os.listdir(REFS)]:
            text = read(doc)
            self.assertNotRegex(text, r"echo \$GIT_TIMESHEET_\w*TOKEN", doc)
            self.assertNotRegex(text, r'-u "\{?apiToken', doc)
            self.assertNotIn("/home/agent", text)
        self.assertNotIn("~/.claude/skills/timesheet/profiles", self.text)

    def test_scripts_are_executable(self):
        for f in os.listdir(helpers.SCRIPTS):
            if f.endswith(".py"):
                self.assertTrue(os.access(os.path.join(helpers.SCRIPTS, f), os.X_OK), f)


if __name__ == "__main__":
    unittest.main()
