import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_voice.brain import build_command, build_env, text_delta


class Safety(unittest.TestCase):
    def test_no_tools_no_mcp_no_saved_session(self):
        command = build_command()
        self.assertEqual(command[command.index("--tools") + 1], "")
        self.assertIn("--strict-mcp-config", command)
        self.assertIn("--no-session-persistence", command)

    def test_an_api_key_in_the_environment_is_never_passed_on(self):
        env = build_env({"HOME": "/h", "ANTHROPIC_API_KEY": "x", "ANTHROPIC_AUTH_TOKEN": "y", "PATH": "/bin"})
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], "/h/.claude-jorah")
        self.assertEqual(env["PATH"], "/bin")


class Parsing(unittest.TestCase):
    def line(self, event):
        return json.dumps({"type": "stream_event", "event": event})

    def test_text(self):
        line = self.line({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}})
        self.assertEqual(text_delta(line), "Hi")

    def test_thinking_is_never_spoken(self):
        line = self.line({"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "hmm"}})
        self.assertIsNone(text_delta(line))

    def test_other_lines_and_garbage(self):
        self.assertIsNone(text_delta(json.dumps({"type": "system"})))
        self.assertIsNone(text_delta("not json"))


if __name__ == "__main__":
    unittest.main()
