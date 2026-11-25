"""Jorah's bootstrap files must reach his context whole.

OpenClaw 2026.10.9 injects each workspace bootstrap file up to bootstrapMaxChars (default 20,000,
per agent in agents.entries.<id>), counted in UTF-16 code units after trimEnd(), and cuts the rest.
USER.md has a fixed 4,000 cap and all files together 60,000. These tests fail at 90% of each
limit, so a growing rules file is caught in `just check` before OpenClaw truncates it.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATCH = ROOT / "config/pc/bootstrap-limit.patch.json5"
# Since 2026-11-25 deep works in main's workspace with its own limit in this patch.
DEEP_PATCH = ROOT / "config/pc/deep-consult.patch.json5"
DEFAULT_MAX = 20_000
USER_MAX = 4_000
TOTAL_MAX = 60_000
MARGIN = 0.9
FILES = ("AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "HEARTBEAT.md", "BOOTSTRAP.md")
WORKSPACES = {"main": "workspace", "deep": "workspace", "background": "workspace-background"}


def chars(path):
    return len(path.read_text(encoding="utf-8").rstrip().encode("utf-16-le")) // 2


def main_limit(patch=PATCH):
    text = re.sub(r"^\s*//.*$", "", patch.read_text(encoding="utf-8"), flags=re.M)
    found = re.findall(r"bootstrapMaxChars:\s*(\d+)", text)
    if len(found) != 1:
        raise AssertionError(f"{patch.name}: expected one bootstrapMaxChars, found {found}")
    return int(found[0])


class BootstrapBudget(unittest.TestCase):
    def limits(self):
        return {"main": main_limit(), "deep": main_limit(DEEP_PATCH), "background": DEFAULT_MAX}

    def test_each_file_fits_with_margin(self):
        for agent, folder in WORKSPACES.items():
            for name in FILES:
                path = ROOT / folder / name
                if not path.is_file():
                    continue
                cap = min(USER_MAX, self.limits()[agent]) if name == "USER.md" else self.limits()[agent]
                with self.subTest(file=f"{folder}/{name}"):
                    self.assertLessEqual(
                        chars(path), int(cap * MARGIN),
                        f"{folder}/{name} is {chars(path)} chars; OpenClaw cuts it at {cap}. Shorten it, "
                        f"or raise the limit in {PATCH.name} on Adam's yes.")

    def test_total_fits(self):
        for agent, folder in WORKSPACES.items():
            total = sum(chars(ROOT / folder / n) for n in FILES if (ROOT / folder / n).is_file())
            with self.subTest(agent=agent):
                # USER.md, MEMORY.md and memory/ are private and not in the repo: keep room for them.
                self.assertLessEqual(total + USER_MAX + 10_000, TOTAL_MAX)

    def test_deep_reads_main_rules_whole(self):
        self.assertGreaterEqual(main_limit(DEEP_PATCH), main_limit())

    def test_main_limit_is_raised_only_for_main(self):
        self.assertGreater(main_limit(), DEFAULT_MAX)
        self.assertIn("main:", PATCH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
