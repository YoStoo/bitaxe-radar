"""Guide kit: small HTML building blocks and SVG diagrams for the skimmable guides (/guides/* and /best/heating-a-room/).

Pure functions that return HTML strings. Callers pass text that is already escaped (or plain literals).
Styles live in site/style.css under "guide kit". Motion is CSS-only and switched off for prefers-reduced-motion;
motion.js adds .rv / .is-in to [data-reveal] sections, so every item is fully visible without JavaScript.
"""


def hero(h1, lede, chips=(), art="", extra=""):
    chip_html = "".join(f'<li class="{c[0]}">{c[1]}</li>' if isinstance(c, tuple) else f"<li>{c}</li>" for c in chips)
    art_html = f'<div class="g-hero-art" aria-hidden="true">{art}</div>' if art else ""
    return (f'<header class="hero g-hero"><div class="g-hero-txt"><h1>{h1}</h1><p class="lede">{lede}</p>'
            + (f'<ul class="g-chips">{chip_html}</ul>' if chips else "") + f"{extra}</div>{art_html}</header>")


def tldr(items, label="Short answer"):
    lis = "".join(f"<li>{i}</li>" for i in items)
    return f'<div class="g-tldr" role="note"><p class="g-tldr-h"><span aria-hidden="true">⚡</span> {label}</p><ul>{lis}</ul></div>'


def section(sid, title, inner, kicker=""):
    k = f'<p class="g-kicker">{kicker}</p>' if kicker else ""
    return f'<section class="g-sec" aria-labelledby="{sid}" data-reveal>{k}<h2 id="{sid}">{title}</h2>{inner}</section>'


def steps(items):
    """items: (title, text) or (emoji, title, text). Numbered step cards joined by a line."""
    out = []
    for i, it in enumerate(items, 1):
        ic, t, x = (it if len(it) == 3 else ("", *it))
        icon = f'<span class="g-step-ic" aria-hidden="true">{ic}</span>' if ic else ""
        out.append(f'<li data-reveal-item><span class="g-n" aria-hidden="true">{i}</span>{icon}<b>{t}</b><span>{x}</span></li>')
    return f'<ol class="g-steps">{"".join(out)}</ol>'


def cards(items):
    """items: (emoji, title, text, tone) with tone in orange/blue/green/purple/yellow/red."""
    out = "".join(f'<div class="g-card t-{tone}" data-reveal-item><span class="g-ic" aria-hidden="true">{ic}</span><b>{t}</b><p>{x}</p></div>'
                  for ic, t, x, tone in items)
    return f'<div class="g-cards n{len(items)}">{out}</div>'


def vs(left, right):
    """Two side-by-side cards: each (emoji, title, tagline, [bullets], tone)."""
    def one(c):
        ic, t, tag, bullets, tone = c
        lis = "".join(f"<li>{b}</li>" for b in bullets)
        return f'<div class="g-vs-card t-{tone}" data-reveal-item><span class="g-ic" aria-hidden="true">{ic}</span><b>{t}</b><p class="g-vs-tag">{tag}</p><ul>{lis}</ul></div>'
    return f'<div class="g-vs">{one(left)}<span class="g-vs-or" aria-hidden="true">vs</span>{one(right)}</div>'


def fig(svg, caption):
    return f'<figure class="g-fig">{svg}<figcaption>{caption}</figcaption></figure>'


def bars(rows, vmax, marker=None, caption=""):
    """Horizontal bar chart. rows: (label_html, value, shown_text, tone). marker: (value, label) drawn as a dashed line."""
    out = []
    for label, v, shown, tone in rows:
        w = 0 if vmax <= 0 else max(1.5, min(100, v / vmax * 100))
        out.append(f'<div class="g-bar" data-reveal-item><span class="g-bl">{label}</span><span class="g-bt"><i class="t-{tone}" style="--w:{w:.1f}%"></i></span><b>{shown}</b></div>')
    cls, style, legend = "g-bars", "", ""
    if marker:
        mv, ml = marker
        cls += " g-has-mark"
        style = f' style="--m:{min(100, mv / vmax * 100):.1f}%"'
        legend = f'<p class="g-mark-legend"><i aria-hidden="true"></i>{ml}</p>'
    cap = f'<p class="hint">{caption}</p>' if caption else ""
    return f'{legend}<div class="{cls}"{style}>{"".join(out)}</div>{cap}'


def faq(items, esc):
    det = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in items)
    return f'<section class="g-sec" aria-labelledby="h-faq"><h2 id="h-faq">Quick questions</h2>{det}</section>'


def more(links, note=""):
    lis = "".join(f'<li><a href="{h}">{t}</a></li>' for h, t in links)
    n = f'<p class="hint">{note}</p>' if note else ""
    return f'<section class="g-sec g-more"><h2>Keep reading</h2><ul class="links">{lis}</ul>{n}</section>'


# ---------------------------------------------------------------------------------------------
# SVG diagrams. Plain shapes, brand colours, text inherits the page font. All decorative motion is CSS.
# ---------------------------------------------------------------------------------------------
def _svg(vb, body, label):
    return f'<svg class="g-svg" viewBox="{vb}" role="img" aria-label="{label}" focusable="false">{body}</svg>'


MINER_BOX = ('<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#16223d" stroke="#f7931a" stroke-width="2"/>'
             '<circle cx="{cx}" cy="{cy}" r="{r}" fill="#0c1324" stroke="#5b74a6" stroke-width="2"/>'
             '<g class="g-spin" style="transform-origin:{cx}px {cy}px"><path d="M{cx} {cy}l0 -{r2}M{cx} {cy}l{r3} {r4}M{cx} {cy}l-{r3} {r4}" stroke="#8fb0ff" stroke-width="3" stroke-linecap="round"/></g>'
             '<circle cx="{lx}" cy="{ly}" r="3" fill="#34d399" class="g-blink"/>')


def miner_box(x, y, w=86, h=70):
    cx, cy, r = x + w * 0.42, y + h / 2, min(w, h) * 0.3
    return MINER_BOX.format(x=x, y=y, w=w, h=h, cx=cx, cy=cy, r=r, r2=r * 0.8, r3=r * 0.7, r4=r * 0.4, lx=x + w - 12, ly=y + 12)


def solar_svg(panel_kwh):
    sun = ('<g class="g-spin-slow" style="transform-origin:60px 92px">' + "".join(
        f'<line x1="{60 + 33 * c:.1f}" y1="{92 + 33 * s:.1f}" x2="{60 + 45 * c:.1f}" y2="{92 + 45 * s:.1f}" stroke="#ffb04d" stroke-width="3.5" stroke-linecap="round"/>'
        for c, s in ((1, 0), (.71, .71), (0, 1), (-.71, .71), (-1, 0), (-.71, -.71), (0, -1), (.71, -.71))) + "</g>"
        '<circle cx="60" cy="92" r="24" fill="#f7931a" class="g-pulse" style="transform-origin:60px 92px"/>')
    panel = ('<path d="M168 120 L196 58 L292 58 L264 120 Z" fill="#1b3a7a" stroke="#8fb0ff" stroke-width="2"/>'
             '<path d="M180 92 L278 92 M190 74 L286 74 M188 104 L272 104 M200 58 L172 120 M232 58 L204 120 M264 58 L236 120" stroke="#8fb0ff" stroke-opacity=".5" stroke-width="1.2"/>'
             '<path d="M228 120 v16 M210 136 h36" stroke="#5b74a6" stroke-width="3"/>')
    batt = ('<rect x="352" y="62" width="84" height="58" rx="9" fill="#16223d" stroke="#34d399" stroke-width="2"/><rect x="436" y="80" width="6" height="22" rx="2" fill="#34d399"/>'
            '<rect x="362" y="72" width="52" height="38" rx="4" fill="#34d399" fill-opacity=".25"/><rect x="362" y="72" width="52" height="38" rx="4" fill="#34d399" class="g-charge"/>')
    flow = ('<path class="g-flow" d="M98 92 H160" stroke="#ffb04d"/><path class="g-flow" d="M296 90 H346" stroke="#ffb04d"/>'
            '<path class="g-flow" d="M448 90 H500" stroke="#34d399"/>')
    labels = ('<text x="60" y="160" text-anchor="middle">Sun</text><text x="60" y="178" text-anchor="middle" class="g-sub">~3 to 6.5 h a day</text>'
              '<text x="230" y="160" text-anchor="middle">Solar panel</text>'
              f'<text x="230" y="178" text-anchor="middle" class="g-sub">400 W ≈ {panel_kwh:.2f} kWh/day</text>'
              '<text x="396" y="160" text-anchor="middle">Battery / power station</text><text x="396" y="178" text-anchor="middle" class="g-sub">only for night-time mining</text>'
              '<text x="552" y="160" text-anchor="middle">Miner</text><text x="552" y="178" text-anchor="middle" class="g-sub">uses watts × 24 h</text>')
    return _svg("0 0 640 196", sun + panel + batt + flow + miner_box(508, 56) + labels, "Sunlight goes into a solar panel, through a battery or power station, into the miner")


def heat_room_svg(watts=1000):
    btu = watts * 3.412
    art = "an" if str(int(watts))[0] == "8" else "a"
    room = ('<path d="M40 60 L320 14 L600 60 V226 H40 Z" fill="#0f1830" stroke="#24324f" stroke-width="2"/>'
            '<rect x="40" y="226" width="560" height="10" fill="#24324f"/>'
            '<rect x="490" y="80" width="70" height="56" rx="4" fill="#0b1222" stroke="#5b74a6" stroke-width="2"/><path d="M525 80 V136 M490 108 H560" stroke="#5b74a6" stroke-width="2"/>')
    warm = ('<defs><radialGradient id="gWarm"><stop offset="0" stop-color="#f7931a" stop-opacity=".32"/><stop offset="1" stop-color="#f7931a" stop-opacity="0"/></radialGradient></defs>'
            '<ellipse cx="250" cy="160" rx="210" ry="80" fill="url(#gWarm)"/>')
    plug = '<path class="g-flow" d="M46 206 H96" stroke="#fbbf24"/>'
    miner = miner_box(100, 152, 96, 70)
    waves = "".join(f'<path class="g-rise" style="animation-delay:{d}s" d="M{x} 146 q 10 -14 0 -28 q -10 -14 0 -28 q 10 -14 0 -28" stroke="#f7931a" stroke-width="3" fill="none" stroke-linecap="round"/>'
                    for x, d in ((126, 0), (148, .6), (170, 1.2)))
    therm = ('<rect x="434" y="150" width="14" height="58" rx="7" fill="#0b1222" stroke="#97a3bb" stroke-width="2"/><circle cx="441" cy="212" r="10" fill="#f87171"/>'
             '<rect x="438" y="166" width="6" height="44" rx="3" fill="#f87171" class="g-therm"/>')
    labels = (f'<text x="330" y="104" text-anchor="middle" class="g-h">≈ {watts:,.0f} W of heat out</text>'
              f'<text x="330" y="126" text-anchor="middle" class="g-sub">≈ {btu:,.0f} BTU/h, like {art} {watts:,.0f} W space heater</text>'
              f'<text x="46" y="256" class="g-sub">⚡ {watts:,.0f} W of electricity in</text>'
              '<text x="594" y="256" text-anchor="end" class="g-sub">+ a small ₿ pool payback</text>')
    return _svg("0 0 640 266", warm + room + plug + miner + waves + therm + labels, f"A miner plugged into the wall turns about {watts:,.0f} watts of electricity into about the same amount of heat in the room")


def solo_pool_svg():
    left = ('<rect x="10" y="10" width="300" height="200" rx="16" fill="#131d35" stroke="#24324f"/>'
            '<text x="160" y="40" text-anchor="middle" class="g-h">🎟 Solo</text>' + miner_box(36, 92, 76, 60)
            + '<path class="g-flow" d="M118 122 H186" stroke="#f7931a"/>'
            '<rect x="194" y="86" width="86" height="72" rx="10" fill="#f7931a" class="g-pulse" style="transform-origin:237px 122px"/>'
            '<text x="237" y="118" text-anchor="middle" class="g-ink">Whole block</text><text x="237" y="138" text-anchor="middle" class="g-ink">≈3.125 BTC</text>'
            '<text x="160" y="190" text-anchor="middle" class="g-sub">all of it, or (usually) nothing</text>')
    minis = "".join(f'<rect x="{352 + i * 50}" y="{60 + (i % 2) * 8}" width="34" height="26" rx="5" fill="#16223d" stroke="#8fb0ff" stroke-width="1.5"/>' for i in range(5))
    lines = "".join(f'<path class="g-flow" d="M{369 + i * 50} {88 + (i % 2) * 8} L480 128" stroke="#8fb0ff"/>' for i in range(5))
    right = ('<rect x="330" y="10" width="300" height="200" rx="16" fill="#131d35" stroke="#24324f"/>'
             '<text x="480" y="40" text-anchor="middle" class="g-h">🤝 Pool</text>' + minis + lines
             + '<circle cx="480" cy="140" r="20" fill="#8fb0ff"/><text x="480" y="145" text-anchor="middle" class="g-ink">pool</text>'
             + "".join(f'<circle cx="{420 + i * 30}" cy="182" r="7" fill="#fbbf24" class="g-coin" style="animation-delay:{i * .25}s"/>' for i in range(5))
             + '<text x="480" y="204" text-anchor="middle" class="g-sub">small, steady share for everyone</text>')
    return _svg("0 0 640 220", left + right, "Solo: one miner tries for a whole block. Pool: many miners share every block the pool finds")


def temp_scale_svg(target, asic_stop, vr_stop):
    lo, hi = 30, 110
    x = lambda t: 30 + (t - lo) / (hi - lo) * 580
    body = ('<defs><linearGradient id="gTemp" x1="0" x2="1"><stop offset="0" stop-color="#34d399"/><stop offset=".45" stop-color="#34d399"/>'
            '<stop offset=".6" stop-color="#fbbf24"/><stop offset=".72" stop-color="#f87171"/><stop offset="1" stop-color="#f87171"/></linearGradient></defs>'
            f'<rect x="30" y="58" width="580" height="18" rx="9" fill="url(#gTemp)"/>')
    for t, lab, sub, y in ((target, f"{target}°C", "fan aims here", 40), (asic_stop, f"{asic_stop}°C", "chip: mining stops", 40), (vr_stop, f"{vr_stop}°C", "regulator: stops", 40)):
        body += (f'<path d="M{x(t):.0f} 50 V84" stroke="#eef2fa" stroke-width="2.5"/><text x="{x(t):.0f}" y="{y - 4}" text-anchor="middle">{lab}</text>'
                 f'<text x="{x(t):.0f}" y="104" text-anchor="middle" class="g-sub">{sub}</text>')
    body += '<text x="30" y="128" class="g-sub">cool</text><text x="610" y="128" text-anchor="end" class="g-sub">too hot</text>'
    return _svg("0 0 640 136", body, f"Temperature scale: the fan aims for {target}°C, mining stops above {asic_stop}°C on the chip or {vr_stop}°C on the voltage regulator")


def plugs_svg():
    barrel = ('<rect x="20" y="20" width="290" height="150" rx="16" fill="#131d35" stroke="#24324f"/>'
              '<text x="165" y="50" text-anchor="middle" class="g-h">5V</text>'
              '<rect x="60" y="80" width="120" height="34" rx="8" fill="#2a3550"/><rect x="180" y="86" width="40" height="22" rx="4" fill="#97a3bb"/>'
              '<circle cx="232" cy="97" r="13" fill="#0b1222" stroke="#97a3bb" stroke-width="3"/><circle cx="232" cy="97" r="3.5" fill="#97a3bb"/>'
              '<path d="M20 97 H60" stroke="#2a3550" stroke-width="8"/>'
              '<text x="165" y="146" text-anchor="middle" class="g-sub">round 5.5 × 2.1 mm barrel plug</text>')
    xt30 = ('<rect x="330" y="20" width="290" height="150" rx="16" fill="#131d35" stroke="#24324f"/>'
            '<text x="475" y="50" text-anchor="middle" class="g-h">12V</text>'
            '<path d="M340 90 H400 M340 104 H400" stroke="#f87171" stroke-width="5"/><path d="M340 104 H400" stroke="#0b1222" stroke-width="5"/>'
            '<path d="M400 76 H500 L512 88 V118 H400 Z" fill="#fbbf24"/><rect x="512" y="84" width="22" height="9" rx="2" fill="#c9cdd6"/><rect x="512" y="101" width="22" height="9" rx="2" fill="#c9cdd6"/>'
            '<text x="475" y="146" text-anchor="middle" class="g-sub">yellow XT30 plug</text>')
    return _svg("0 0 640 186", barrel + xt30, "5V boards use a round barrel plug; 12V boards use a yellow XT30 plug")


def monitor_svg():
    house = ('<path d="M20 90 L190 20 L360 90 V230 H20 Z" fill="#0f1830" stroke="#24324f" stroke-width="2"/>'
             '<text x="190" y="66" text-anchor="middle" class="g-sub">at home (same Wi-Fi)</text>')
    router = ('<rect x="150" y="120" width="80" height="30" rx="6" fill="#16223d" stroke="#8fb0ff" stroke-width="2"/>'
              '<path d="M170 120 V100 M210 120 V100" stroke="#8fb0ff" stroke-width="2"/><text x="190" y="170" text-anchor="middle" class="g-sub">router</text>')
    phone = lambda x, y, txt: (f'<rect x="{x}" y="{y}" width="40" height="70" rx="8" fill="#16223d" stroke="#34d399" stroke-width="2"/>'
                                f'<rect x="{x + 6}" y="{y + 10}" width="28" height="44" rx="3" fill="#0b1222"/><path d="M{x + 10} {y + 40} l6 -8 l6 4 l8 -12" stroke="#34d399" stroke-width="2" fill="none"/>'
                                f'<text x="{x + 20}" y="{y + 88}" text-anchor="middle" class="g-sub">{txt}</text>')
    cloud = ('<path d="M430 90 a26 26 0 0 1 50 -10 a22 22 0 0 1 40 14 a18 18 0 0 1 -6 36 h-80 a20 20 0 0 1 -4 -40 z" fill="#18243f" stroke="#8fb0ff" stroke-width="2"/>'
             '<text x="470" y="116" text-anchor="middle" class="g-sub">pool stats page</text>')
    flows = ('<path class="g-flow" d="M126 160 H150" stroke="#8fb0ff"/><path class="g-flow" d="M230 135 H270" stroke="#34d399"/>'
             '<path class="g-flow" d="M230 128 C 300 60 380 70 420 96" stroke="#8fb0ff"/><path class="g-flow" d="M500 130 V160 H540" stroke="#34d399"/>')
    body = house + miner_box(40, 130, 84, 64) + router + phone(272, 100, "dashboard") + cloud + phone(546, 130, "away from home") + flows
    return _svg("0 0 640 250", body, "At home your phone reads the miner over Wi-Fi; away from home, check your pool's stats page")


def bitaxe_screen_svg():
    qr = "".join(f'<rect x="{236 + (i % 6) * 9}" y="{60 + (i // 6) * 9}" width="8" height="8" fill="#eef2fa"/>'
                 for i in range(36) if (i * 7 + i // 6) % 3 != 1)
    body = ('<rect x="20" y="20" width="300" height="140" rx="14" fill="#16223d" stroke="#f7931a" stroke-width="2"/>'
            '<rect x="36" y="40" width="268" height="100" rx="6" fill="#0b1222" stroke="#5b74a6"/>'
            '<text x="52" y="72" class="g-mono">Wi-Fi: Bitaxe_1A2B</text><text x="52" y="96" class="g-mono g-sub">scan to set up →</text>'
            '<text x="52" y="120" class="g-mono g-sub">IP shows here later</text>' + qr
            + '<circle cx="300" cy="40" r="4" fill="#34d399" class="g-blink"/>')
    return _svg("0 0 340 180", body, "The Bitaxe screen shows a setup Wi-Fi name like Bitaxe_1A2B and a QR code")
