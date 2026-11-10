"""Anthropic Messages API client (standard library only, so the GitHub Action needs no pip install).

Model and API version are READ from worker/src/ask.js, so the deal agent always uses the same Claude
setup as the Ask chat: change it there, both follow. The key comes from the ANTHROPIC_API_KEY
environment variable (a GitHub Actions secret). It is never printed, logged or written to a file.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_ASK_JS = (ROOT / "worker" / "src" / "ask.js").read_text()
MODEL = re.search(r'export const DEFAULT_MODEL = "([^"]+)"', _ASK_JS).group(1)
API_VERSION = re.search(r'const ANTHROPIC_VERSION = "([^"]+)"', _ASK_JS).group(1)
API_URL = "https://api.anthropic.com/v1/messages"

# Price of the model, US dollars per million tokens (same numbers as docs/TOOL_CALLING.md).
USD_PER_M_IN = 0.10
USD_PER_M_OUT = 0.50


def cost_usd(usage):
    return usage.get("input_tokens", 0) * USD_PER_M_IN / 1e6 + usage.get("output_tokens", 0) * USD_PER_M_OUT / 1e6


class ClaudeError(Exception):
    """The API call failed (no key, network, HTTP error). The agent keeps yesterday's deal."""


class Claude:
    """call(body) -> the API's JSON reply. Tests swap this for a fake with the same method."""

    def __init__(self, api_key=None, timeout=30):
        self.api_key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY", "")
        self.timeout = timeout

    def call(self, body):
        if not self.api_key:
            raise ClaudeError("ANTHROPIC_API_KEY is not set")
        req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST", headers={
            "content-type": "application/json", "x-api-key": self.api_key, "anthropic-version": API_VERSION})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")
            except Exception:
                msg = ""
            raise ClaudeError(f"Claude HTTP {e.code}: {msg[:200]}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise ClaudeError(f"Claude call failed: {type(e).__name__}") from None
