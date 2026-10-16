#!/usr/bin/env python3
"""Copy collector output into the static site as site/data.js (works on any static host and file://)."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
latest = json.loads((ROOT / "data" / "latest.json").read_text())
history = json.loads((ROOT / "data" / "history.json").read_text())
latest = dict(latest, unscrapable=[u for u in latest["unscrapable"] if not u.get("internal")])
payload = {"latest": latest, "history": history}
(ROOT / "site" / "data.js").write_text("window.RADAR = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
print("wrote site/data.js:", len(latest["offers"]), "offers,", len(history), "history series")
