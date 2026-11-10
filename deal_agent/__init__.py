"""Deal of the Day agent: picks the best real deal from our price data and writes a short, checked summary.

Plain-English guide: docs/DEAL_AGENT.md.

  facts.py     the numbers (today's offers + SQL price history), computed by plain code
  tools.py     the tools Claude may call, and their JSON schemas
  claude.py    the Anthropic API client (same model and API version as the Ask chat Worker)
  guard.py     the grounding check: every price, % and shop in the output must match the data
  template.py  the no-AI fallback writer (used when the AI's output fails the check twice)
  agent.py     the tool loop: ask Claude, run its tools, repeat, verify, retry once, fall back
  __main__.py  the daily command: python3 -m deal_agent
"""
