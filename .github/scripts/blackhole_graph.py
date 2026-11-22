"""Draw the last year of GitHub contributions spiralling into a black hole (animated SVG).

Usage: GITHUB_TOKEN=... python blackhole_graph.py <github-login> <output.svg>

Every contribution square spirals into the black hole in the middle of the grid,
nearest squares first, then the grid rebuilds and the loop repeats. Pure CSS
animation, no filters, so it stays light enough to draw at 60 fps.
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
CYCLE = 14  # seconds per eat-and-rebuild loop


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
    rng = random.Random(7)

    cells = []
    for ci, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = left + ci * step + cell / 2
            y = top + day["weekday"] * step + cell / 2
            cells.append((x - hx, y - hy, COLORS.get(day["contributionLevel"], COLORS["NONE"])))
    far = max(math.hypot(dx, dy) for dx, dy, _ in cells)

    rects = []
    for dx, dy, color in cells:
        d = math.hypot(dx, dy) / far
        delay = d ** 0.8 * 3.4 + rng.uniform(0, .25)
        turn = 240 + rng.uniform(0, 140)
        rects.append(
            f'<rect x="-5.5" y="-5.5" width="11" height="11" rx="2" fill="{color}" '
            f'style="--dx:{dx:.1f}px;--dy:{dy:.1f}px;--r:{turn:.0f}deg;animation-delay:{delay:.2f}s"/>')

    at = f"translate({hx:.1f}px,{hy:.1f}px)"
    home = f"{at} rotate(0deg) scale(1) translate(var(--dx),var(--dy))"
    gone = f"{at} rotate(var(--r)) scale(.02) translate(var(--dx),var(--dy))"
    css = f"""
.c rect{{animation:eat {CYCLE}s infinite both}}
@keyframes eat{{
0%,10%{{transform:{home};opacity:1;animation-timing-function:cubic-bezier(.55,0,.95,.45)}}
34%{{opacity:1}}
42%,74%{{transform:{gone};opacity:0}}
75%{{transform:{home};opacity:0}}
86%,100%{{transform:{home};opacity:1}}}}
.hole{{animation:hole {CYCLE}s ease-in-out infinite both}}
@keyframes hole{{0%,12%{{transform:{at} scale(1)}}45%{{transform:{at} scale(1.45)}}55%{{transform:{at} scale(1.6)}}70%,100%{{transform:{at} scale(1)}}}}
.flash{{animation:flash {CYCLE}s ease-out infinite both}}
@keyframes flash{{0%,44%{{opacity:0}}50%{{opacity:.9}}66%,100%{{opacity:0}}}}
.tw{{animation:tw 4s ease-in-out infinite both}}@keyframes tw{{50%{{opacity:.15}}}}"""

    stars = "".join(
        f'<circle cx="{rng.uniform(8, W - 8):.0f}" cy="{rng.uniform(8, H - 8):.0f}" r="{rng.uniform(.3, 1):.1f}" fill="#fff" '
        f'opacity=".7"{" class=" + chr(34) + "tw" + chr(34) if rng.random() < .3 else ""} style="animation-delay:-{rng.uniform(0, 4):.1f}s"/>'
        for _ in range(45))

    disk = ""
    for i, (rx, color, dur) in enumerate([(30, "#fde68a", 1.6), (40, "#f59e0b", 2.4), (50, "#c2410c", 3.4)]):
        dash = rx * .5
        disk += (f'<ellipse rx="{rx}" ry="{rx * .24:.1f}" fill="none" stroke="{color}" stroke-width="{2.6 - i * .6:.1f}" '
                 f'stroke-linecap="round" stroke-dasharray="{dash:.0f} {rx * .2:.0f}" opacity=".9">'
                 f'<animate attributeName="stroke-dashoffset" values="0;-{(dash + rx * .2) * 4:.0f}" dur="{dur}s" repeatCount="indefinite"/></ellipse>')

    total = cal["totalContributions"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><radialGradient id="g"><stop offset=".2" stop-color="#f97316" stop-opacity=".55"/><stop offset="1" stop-color="#f97316" stop-opacity="0"/></radialGradient>
<radialGradient id="fl"><stop offset="0" stop-color="#fff7ed"/><stop offset=".4" stop-color="#fde68a" stop-opacity=".6"/><stop offset="1" stop-color="#fde68a" stop-opacity="0"/></radialGradient></defs>
<style>{css}</style>
<rect width="{W}" height="{H}" rx="10" fill="#000"/>
{stars}
<text x="{left:.0f}" y="30" font-family="{MONO}" font-size="11" letter-spacing="3" fill="#a8a29e">CONTRIBUTIONS · LAST 12 MONTHS</text>
<text x="{left + gw:.0f}" y="30" text-anchor="end" font-family="{MONO}" font-size="11" letter-spacing="2" fill="#fbbf24">{total} ABSORBED</text>
<g class="c">{"".join(rects)}</g>
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
