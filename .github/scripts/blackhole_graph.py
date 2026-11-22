"""Draw the last year of GitHub contributions being eaten by a black hole (animated SVG).

Usage: GITHUB_TOKEN=... python blackhole_graph.py <github-login> <output.svg>

Each 16 s loop:
  1. a drop lands on the middle of the grid and a water ripple spreads out
  2. the ripple distorts every square as it passes (push out, pull back, swell, shrink)
  3. a black hole spawns at the drop point and grows, swallowing the nearest squares as it grows
  4. once every square is gone the hole shrinks away, the grid respawns from the centre out, repeat

Squares are grouped into distance bands from the centre; each band has its own keyframes, so
timing spreads outward like a real wave while the file stays small. Pure CSS, no filters.
"""
import json
import math
import os
import random
import sys
import urllib.request
from pathlib import Path

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount contributionLevel weekday } }
      }
    }
  }
}"""

COLORS = {  # Event Horizon palette, dim to bright
    "NONE": "#1c1917",
    "FIRST_QUARTILE": "#7c2d12",
    "SECOND_QUARTILE": "#c2410c",
    "THIRD_QUARTILE": "#f59e0b",
    "FOURTH_QUARTILE": "#fde68a",
}
SANS = "'Segoe UI','Helvetica Neue',Helvetica,Arial,sans-serif"
MONO = "'Courier New',Consolas,Menlo,monospace"

T = 16.0          # seconds per loop
BANDS = 36        # distance bands (more = smoother spread, bigger file)
DROP = 0.0        # drop lands
WAVE = (0.35, 2.4)  # ripple starts, seconds to reach the farthest square
SPAWN = 3.6       # black hole appears
EAT = (3.9, 6.2)  # first square starts falling, spread until the last one does
FALL = 1.5        # seconds a square takes to spiral in
SHRINK = (11.7, 13.0)
RESPAWN = (13.1, 1.1)  # respawn starts, spread from centre to edge
RIPPLE = [(0, 0, 1), (.15, 1, 1.28), (.35, -.6, .82), (.55, .32, 1.12), (.75, -.14, .94), (.95, 0, 1)]  # (dt, push, size)


def pct(t):
    return f"{max(0.0, min(100.0, t / T * 100)):.3f}%"


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "blackhole-graph"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"GitHub API error: {body['errors']}")
    return body["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def render(cal):
    weeks = cal["weeks"]
    cell, gap = 11, 3
    step = cell + gap
    gw, gh = len(weeks) * step - gap, 7 * step - gap
    W, top = 900, 48
    H = top + gh + 44
    left = (W - gw) / 2
    hx, hy = W / 2, top + gh / 2
    H_AT = f"translate({hx:.1f}px,{hy:.1f}px)"
    rng = random.Random(7)

    cells = []
    for ci, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = left + ci * step + cell / 2
            y = top + day["weekday"] * step + cell / 2
            cells.append((x - hx, y - hy, COLORS.get(day["contributionLevel"], COLORS["NONE"])))
    far = max(math.hypot(dx, dy) for dx, dy, _ in cells)

    def tf(k=0, r="0deg", s="1", q="1"):
        # hole centre -> spin -> pull toward hole -> home position (+ ripple push) -> square's own size
        return (f"{H_AT} rotate({r}) scale({s}) "
                f"translate(calc(var(--dx) + var(--ux) * {k}),calc(var(--dy) + var(--uy) * {k})) scale({q})")

    css = [".c rect{animation-duration:%ss;animation-iteration-count:infinite;animation-fill-mode:both}" % T]
    for b in range(BANDS):
        u = (b + .5) / BANDS
        tw = WAVE[0] + u * WAVE[1]
        ts = EAT[0] + u ** .9 * EAT[1]
        tr = RESPAWN[0] + u * RESPAWN[1]
        st = [f"0%{{transform:{tf()};opacity:1}}"]
        for dt, k, q in RIPPLE:
            st.append(f"{pct(tw + dt)}{{transform:{tf(k, q=q)};animation-timing-function:ease-in-out}}")
        st.append(f"{pct(ts)}{{transform:{tf()};opacity:1;animation-timing-function:cubic-bezier(.5,0,.95,.5)}}")
        st.append(f"{pct(ts + FALL * .75)}{{opacity:1}}")
        st.append(f"{pct(ts + FALL)},{pct(tr - .02)}{{transform:{tf(r='var(--r)', s='.02')};opacity:0}}")
        st.append(f"{pct(tr)}{{transform:{tf(q='.3')};opacity:0;animation-timing-function:cubic-bezier(.2,.8,.3,1.2)}}")
        st.append(f"{pct(tr + .6)},100%{{transform:{tf()};opacity:1}}")
        css.append(f".b{b}{{animation-name:k{b}}}@keyframes k{b}{{{''.join(st)}}}")

    rects = []
    for dx, dy, color in cells:
        d = math.hypot(dx, dy)
        u = d / far
        band = min(BANDS - 1, int(u * BANDS))
        amp = 7 * (1 - .55 * u)
        ux, uy = (amp * dx / d, amp * dy / d) if d > 1 else (0, 0)
        rects.append(
            f'<rect class="b{band}" x="-5.5" y="-5.5" width="11" height="11" rx="2" fill="{color}" '
            f'style="--dx:{dx:.1f}px;--dy:{dy:.1f}px;--ux:{ux:.2f}px;--uy:{uy:.2f}px;--r:{240 + rng.uniform(0, 140):.0f}deg"/>')

    t_end = WAVE[0] + WAVE[1]
    css.append(f"""
.ring{{animation:ring {T}s linear infinite both}}
@keyframes ring{{0%,{pct(WAVE[0])}{{transform:{H_AT} scale(0);opacity:0}}{pct(WAVE[0] + .1)}{{opacity:.85}}
{pct(t_end)},100%{{transform:{H_AT} scale(1);opacity:0}}}}
.drop{{animation:drop {T}s infinite both}}
@keyframes drop{{0%{{transform:{H_AT} scale(0);opacity:0}}{pct(DROP + .18)}{{transform:{H_AT} scale(1.7);opacity:1}}
{pct(DROP + .6)}{{transform:{H_AT} scale(.7);opacity:.8}}{pct(DROP + 1.1)},100%{{transform:{H_AT} scale(.4);opacity:0}}}}
.hole{{animation:hole {T}s infinite both}}
@keyframes hole{{0%,{pct(SPAWN)}{{transform:{H_AT} scale(0);opacity:0;animation-timing-function:cubic-bezier(.2,.7,.4,1)}}
{pct(SPAWN + .15)}{{opacity:1}}{pct(EAT[0] + 2.2)}{{transform:{H_AT} scale(1)}}
{pct(EAT[0] + EAT[1] + .6)},{pct(SHRINK[0])}{{transform:{H_AT} scale(1.6);opacity:1;animation-timing-function:cubic-bezier(.5,0,.8,.6)}}
{pct(SHRINK[1])}{{transform:{H_AT} scale(0);opacity:1}}{pct(SHRINK[1] + .05)},100%{{transform:{H_AT} scale(0);opacity:0}}}}
.flash{{animation:flash {T}s ease-out infinite both}}
@keyframes flash{{0%,{pct(SHRINK[0] - .4)}{{opacity:0}}{pct(SHRINK[0])}{{opacity:.9}}{pct(SHRINK[0] + .8)},100%{{opacity:0}}}}
.tw{{animation:tw 4s ease-in-out infinite both}}@keyframes tw{{50%{{opacity:.15}}}}""")

    stars = "".join(
        f'<circle cx="{rng.uniform(8, W - 8):.0f}" cy="{rng.uniform(8, H - 8):.0f}" r="{rng.uniform(.3, 1):.1f}" fill="#fff" opacity=".7"'
        + (f' class="tw" style="animation-delay:-{rng.uniform(0, 4):.1f}s"' if rng.random() < .3 else "") + "/>"
        for _ in range(45))
    rings = "".join(
        f'<circle r="{far * 1.08:.0f}" fill="none" stroke="{c}" stroke-width="{sw}" vector-effect="non-scaling-stroke" '
        f'class="ring" style="animation-delay:{dl}s"/>'
        for dl, c, sw in [(0, "#fde68a", 1.8), (.22, "#f59e0b", 1.3), (.44, "#c2410c", 1)])
    disk = ""
    for i, (rx, color, dur) in enumerate([(30, "#fde68a", 1.6), (40, "#f59e0b", 2.4), (50, "#c2410c", 3.4)]):
        dash = rx * .5
        disk += (f'<ellipse rx="{rx}" ry="{rx * .24:.1f}" fill="none" stroke="{color}" stroke-width="{2.6 - i * .6:.1f}" '
                 f'stroke-linecap="round" stroke-dasharray="{dash:.0f} {rx * .2:.0f}" opacity=".9">'
                 f'<animate attributeName="stroke-dashoffset" values="0;-{(dash + rx * .2) * 4:.0f}" dur="{dur}s" repeatCount="indefinite"/></ellipse>')

    total = cal["totalContributions"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><radialGradient id="g"><stop offset=".2" stop-color="#f97316" stop-opacity=".55"/><stop offset="1" stop-color="#f97316" stop-opacity="0"/></radialGradient>
<radialGradient id="fl"><stop offset="0" stop-color="#fff7ed"/><stop offset=".4" stop-color="#fde68a" stop-opacity=".6"/><stop offset="1" stop-color="#fde68a" stop-opacity="0"/></radialGradient>
<radialGradient id="dr"><stop offset="0" stop-color="#fff7ed"/><stop offset=".5" stop-color="#fde68a" stop-opacity=".8"/><stop offset="1" stop-color="#fde68a" stop-opacity="0"/></radialGradient>
<clipPath id="pond"><rect x="{left - 14:.0f}" y="{top - 12}" width="{gw + 28:.0f}" height="{gh + 24}" rx="8"/></clipPath></defs>
<style>{"".join(css)}</style>
<rect width="{W}" height="{H}" rx="10" fill="#000"/>
{stars}
<text x="{left:.0f}" y="30" font-family="{MONO}" font-size="11" letter-spacing="3" fill="#a8a29e">CONTRIBUTIONS · LAST 12 MONTHS</text>
<text x="{left + gw:.0f}" y="30" text-anchor="end" font-family="{MONO}" font-size="11" letter-spacing="2" fill="#fbbf24">{total} ABSORBED</text>
<g clip-path="url(#pond)">{rings}</g>
<g class="c">{"".join(rects)}</g>
<circle r="7" fill="url(#dr)" class="drop"/>
<g class="hole"><circle r="70" fill="url(#g)"/><circle r="46" fill="url(#fl)" class="flash"/>{disk}
<circle r="17" fill="none" stroke="#fde68a" stroke-width="2"/><circle r="15.5" fill="#000"/></g>
<text x="{W / 2}" y="{H - 16}" text-anchor="middle" font-family="{SANS}" font-size="12" letter-spacing="3" fill="#78716c">nothing escapes · not even commits</text>
</svg>"""


if __name__ == "__main__":
    login, out = sys.argv[1], Path(sys.argv[2])
    token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN is not set")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(fetch(login, token)), encoding="utf-8")
    print(f"wrote {out}")
