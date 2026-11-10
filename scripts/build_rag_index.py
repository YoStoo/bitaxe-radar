"""Build the RAG index: split the site's written guides into small passages ("chunks").

Plain-English version: docs/RAG.md.

  python3 build_site.py               # makes site/guides/*/index.html
  python3 scripts/build_rag_index.py  # -> worker/src/rag_chunks.json (committed; the Worker bundles it)

Steps for each page:
  1. Keep only the article (no menus, breadcrumbs, scripts, "Keep reading" link lists).
  2. Drop live numbers that go stale: table columns about prices or money per month, and the "updated" line.
     Prices must come from the price tools, never from a guide passage.
  3. Split by section heading (h2). A long section is cut into pieces of about MAX_CHARS, on sentence
     boundaries, and each piece repeats the last sentence of the one before ("overlap"), so an idea that
     spans a cut is still found whole in at least one chunk.
  4. Every chunk keeps its guide's title, section heading and URL, so the answer can cite it.

The Worker turns each chunk into an embedding (a list of 384 numbers) the first time it needs them
(Workers AI, model bge-small-en-v1.5) and caches them. This script needs no network and no keys.
"""
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = ROOT / "worker" / "src" / "rag_chunks.json"
MAX_CHARS = 900          # ~200 tokens: small enough to be about one thing, big enough to make sense alone
MIN_CHARS = 120          # merge tiny sections into the next one
PAGES = sorted(p.parent for p in (SITE / "guides").glob("*/index.html")) + [SITE / "how-we-track"]
STALE_HEADER = re.compile(r"price|\$|/mo|net|break-?even|earn|cost|cheapest|stock|today", re.I)
SKIP_SECTIONS = re.compile(r"^(keep reading|related|more guides)", re.I)


def text_of(fragment):
    """HTML -> plain text, keeping sentences readable."""
    s = re.sub(r"<(script|style|svg|form|button|input|select)\b[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"</(p|li|h\d|tr|div|dt|dd|summary|details)>", ". ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    s = re.sub(r"([.!?:])\.+", r"\1", s)        # "Short answer:." -> "Short answer:"
    s = re.sub(r"(\.\s*){2,}", ". ", s)
    return s.strip(" .") + "." if s.strip(" .") else ""


def table_text(table_html):
    """Tables -> 'Miner: X; Stated noise: 29 dB' lines, without columns that hold live prices."""
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_html, flags=re.S | re.I)
    if not rows:
        return ""
    header = [text_of(c).rstrip(".") for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", rows[0], flags=re.S | re.I)]
    keep = [i for i, h in enumerate(header) if h and not STALE_HEADER.search(h)]
    if len(keep) < 2:
        return ""                                    # nothing left but the name column: skip the table
    lines = []
    for r in rows[1:]:
        cells = [text_of(c).rstrip(".") for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", r, flags=re.S | re.I)]
        parts = [f"{header[i]}: {cells[i]}" for i in keep if i < len(cells) and cells[i]]
        if parts:
            lines.append("; ".join(parts) + ".")
    return " ".join(lines)


def article(page_html):
    m = re.search(r"<article\b.*?</article>", page_html, flags=re.S | re.I) or re.search(r"<main\b.*?</main>", page_html, flags=re.S | re.I)
    a = m.group(0) if m else page_html
    a = re.sub(r"<nav\b.*?</nav>", " ", a, flags=re.S | re.I)
    a = re.sub(r'<p class="meta".*?</p>', " ", a, flags=re.S | re.I)          # "updated ... · 3-minute read"
    a = re.sub(r"<table\b.*?</table>", lambda t: "<p>" + html.escape(table_text(t.group(0))) + "</p>", a, flags=re.S | re.I)
    return a


def split_sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text) if s.strip()]


def pieces(text, max_chars=MAX_CHARS):
    """Cut long text on sentence boundaries, with a one-sentence overlap between pieces."""
    if len(text) <= max_chars:
        return [text]
    out, cur = [], []
    for s in split_sentences(text):
        if cur and len(" ".join(cur + [s])) > max_chars:
            out.append(" ".join(cur))
            cur = [cur[-1]] if len(cur[-1]) < max_chars // 2 else []   # overlap: repeat the last sentence
        cur.append(s)
    if cur:
        out.append(" ".join(cur))
    return out


def page_chunks(page_dir):
    raw = (page_dir / "index.html").read_text()
    slug = page_dir.name
    url = "/" + str(page_dir.relative_to(SITE)).replace("\\", "/") + "/"
    a = article(raw)
    title_m = re.search(r"<h1\b[^>]*>(.*?)</h1>", a, flags=re.S | re.I)
    title = text_of(title_m.group(1)).rstrip(".") if title_m else slug
    # Split on h2: [intro, h2a, body a, h2b, body b, ...]
    parts = re.split(r"<h2\b[^>]*>(.*?)</h2>", a, flags=re.S | re.I)
    sections = [("Intro", parts[0])] + [(text_of(parts[i]).rstrip("."), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    out, carry, carry_heading = [], "", None
    for heading, body in sections:
        heading = re.sub(r"^\d+\.\s*", "", heading)          # "2. Noise table" -> "Noise table"
        if SKIP_SECTIONS.search(heading):
            continue
        body_html = re.sub(r"<h1\b.*?</h1>", " ", body, flags=re.S | re.I)
        text = (carry + " " + text_of(body_html)).strip()
        if len(text) < MIN_CHARS:
            carry, carry_heading = text, carry_heading or heading   # too short alone: glue it to the next section
            continue
        if carry_heading:
            heading = carry_heading                                   # label it where the text STARTS
        carry, carry_heading = "", None
        for piece in pieces(text):
            out.append({"guide": slug, "title": title, "section": heading, "url": url, "text": piece})
    if carry and out:
        out[-1]["text"] += " " + carry
    for i, c in enumerate(out):
        c["id"] = f"{slug}#{i}"
    return out


def build():
    chunks = []
    for p in PAGES:
        if (p / "index.html").exists():
            chunks += page_chunks(p)
    # The version stamp changes whenever any chunk text changes; the Worker uses it to know when to re-embed.
    version = hashlib.sha256(json.dumps([c["text"] for c in chunks]).encode()).hexdigest()[:16]
    guides = {}
    for c in chunks:
        guides.setdefault(c["guide"], {"title": c["title"], "url": c["url"]})
    return {"version": version, "guides": guides,
            "chunks": [{k: c[k] for k in ("id", "guide", "section", "text")} for c in chunks]}


def main():
    idx = build()
    if not idx["chunks"]:
        sys.exit("No guide pages found. Run python3 build_site.py first.")
    OUT.write_text(json.dumps(idx, indent=1, ensure_ascii=False) + "\n")
    sizes = [len(c["text"]) for c in idx["chunks"]]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(idx['chunks'])} chunks from {len(idx['guides'])} pages, "
          f"{min(sizes)}-{max(sizes)} chars, version {idx['version']}")


if __name__ == "__main__":
    main()
