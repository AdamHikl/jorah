"""The thinking step: one toolless Claude Code call per turn, with the reply streamed back."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

MODEL = "claude-haiku-5-5"

PERSONA = """You are Jorah, Adam's personal assistant, talking out loud. Your pronoun is he.
Keep replies short enough to say in one breath: one to three sentences, unless Adam asks for more.
Be witty and warm for everyday things and when starting the day. Be dry, brief and efficient for work, problems and anything serious.
Your words are read aloud, so use plain sentences with no lists, markdown or emoji. Write numbers the way they are said.
Adam's words come from speech recognition, so a strange word was probably misheard. If a reply depends on it, ask.
Right now you have no tools, no memory of past sessions, and no access to Adam's mail, calendar, files or the web. If asked to do something that needs them, say plainly that you can't yet. Never pretend you did something.
You are your own character. Never imitate a film or a real person."""


def build_command(model=MODEL, persona=PERSONA):
    return [
        "claude", "-p",
        "--model", model,
        "--system-prompt", persona,
        "--tools", "",
        "--strict-mcp-config",
        "--setting-sources", "",
        "--no-session-persistence",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",
    ]


def build_env(base=None):
    """Jorah's own login, and never an API key, which would silently move this to API billing."""
    env = dict(os.environ if base is None else base)
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(name, None)
    env["CLAUDE_CONFIG_DIR"] = str(Path(env.get("HOME", str(Path.home()))) / ".claude-jorah")
    return env


def text_delta(line):
    """Return the text in one stream-json line, or None if the line carries no reply text."""
    try:
        event = json.loads(line)
    except (ValueError, TypeError):
        return None
    if event.get("type") != "stream_event":
        return None
    inner = event.get("event") or {}
    if inner.get("type") != "content_block_delta":
        return None
    delta = inner.get("delta") or {}
    return delta.get("text") if delta.get("type") == "text_delta" else None


class BrainError(RuntimeError):
    pass


class ClaudeBrain:
    def __init__(self, model=MODEL):
        self._model = model
        self._process = None

    def stream(self, prompt):
        """Yield reply text as it arrives. Runs in an empty folder, so there is nothing to read."""
        with tempfile.TemporaryDirectory(prefix="jorah-voice-") as empty:
            self._process = subprocess.Popen(
                build_command(self._model),
                cwd=empty,
                env=build_env(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._process.stdin.write(prompt)
            self._process.stdin.close()
            produced = False
            for line in self._process.stdout:
                text = text_delta(line)
                if text:
                    produced = True
                    yield text
            code = self._process.wait()
            if code not in (0, -15) and not produced:
                raise BrainError(f"claude exited with {code}: {self._process.stderr.read()[:300]}")

    def cancel(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
