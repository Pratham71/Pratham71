"""Build the profile README SVGs into assets/. Run: python scripts/build.py"""
import base64
import io
import json
import os
import subprocess
import tempfile
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT = ASSETS / "fonts" / "MartianMono[wdth,wght].ttf"
MAX_BYTES = 50_000

C = {
    "ink": "#0A0D10", "panel": "#12171C", "line": "#232B33", "text": "#E6EDF3",
    "muted": "#7D8A96", "amber": "#FFB547", "ok": "#3DDC97",
}
FALLBACK = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
LOGIN = os.environ.get("GH_LOGIN", "Pratham71")

CONTENT = {
    "name": "PRATHAM NAGPAL",
    "prompt": "pratham@prathlabs:~",
    "lines": ["infrastructure, devops and backend", "cs @ bits pilani dubai · dxb / del"],
    "status": [("active", "homelab active"), ("shipped", "vessel shipped")],
    "projects": {
        "homelab": {"name": "homelab-infrastructure",
                    "desc": "Multi-node self-hosted stack: Dockerized services, monitoring, remote access over Tailscale.",
                    "lang": "Shell", "status": "active"},
        "vessel": {"name": "Vessel", "desc": "A minimal interactive Java notebook environment.",
                   "lang": "Java", "status": "shipped"},
    },
    "stack": [
        ("build", [("python", "Python"), ("openjdk", "Java"), ("typescript", "TypeScript"), ("fastapi", "FastAPI"),
                   ("nextdotjs", "Next.js"), ("postgresql", "PostgreSQL"), ("mongodb", "MongoDB")]),
        ("run", [("docker", "Docker"), ("debian", "Debian"), ("tailscale", "Tailscale"), ("coolify", "Coolify"),
                 ("grafana", "Grafana"), ("prometheus", "Prometheus"), ("n8n", "n8n"), ("gnubash", "Bash")]),
    ],
}


def esc(s):
    return escape(s, {'"': "&quot;"})


def validate(svg):
    size = len(svg.encode("utf-8"))
    if size >= MAX_BYTES:
        raise ValueError(f"svg is {size} bytes, limit {MAX_BYTES}")
    try:
        ET.fromstring(svg)
    except ET.ParseError as e:
        raise ValueError(f"invalid svg: {e}") from e


def write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
  }
}
"""


def streaks(counts):
    longest = run = 0
    for n in counts:
        run = run + 1 if n else 0
        longest = max(longest, run)
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:  # today isn't over yet
        i -= 1
    current = 0
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    return current, longest


def lang_shares(nodes):
    totals = {}
    for repo in nodes:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
    whole = sum(size for _, size in top)
    return [(name, round(size * 100 / whole, 1)) for name, size in top] if whole else []


def token():
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def fetch(login, tok):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {tok}", "User-Agent": "profile-build"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    user = (body.get("data") or {}).get("user")
    if body.get("errors") or not user:
        raise RuntimeError(f"GraphQL error: {body.get('errors')}")
    return user


def summarize(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    current, longest = streaks([d["contributionCount"] for d in days])
    repos = user["repositories"]
    return {
        "total": cal["totalContributions"], "current": current, "longest": longest,
        "repos": repos["totalCount"], "langs": lang_shares(repos["nodes"]), "updated": days[-1]["date"],
    }


@lru_cache(maxsize=None)
def _instance_bytes(wght, wdth):
    buf = io.BytesIO()
    instantiateVariableFont(TTFont(FONT), {"wght": wght, "wdth": wdth}).save(buf)
    return buf.getvalue()


def _font(wght, wdth):
    return TTFont(io.BytesIO(_instance_bytes(wght, wdth)))


def _check_glyphs(text, font):
    cmap = font.getBestCmap()
    missing = sorted({ch for ch in text if ch != "\n" and ord(ch) not in cmap})
    if missing:
        raise ValueError(f"font lacks glyphs: {missing}")


def font_face(text, family, wght=400, wdth=100):
    font = _font(wght, wdth)
    _check_glyphs(text, font)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []
    opts.name_IDs = []
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(set(text))))
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:{family};src:url(data:font/woff2;base64,{b64}) format('woff2')}}"


def char_w(size, wght=400, wdth=100):
    font = _font(wght, wdth)
    return font["hmtx"][font.getBestCmap()[ord("0")]][0] * size / font["head"].unitsPerEm


def name_path(text, size, wght=800, wdth=112.5):
    font = _font(wght, wdth)
    _check_glyphs(text, font)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    k = size / font["head"].unitsPerEm
    pen = SVGPathPen(glyphs, ntos=lambda v: format(round(v, 1), "g"))
    x = 0.0
    for ch in text:
        g = glyphs[cmap[ord(ch)]]
        g.draw(TransformPen(pen, (k, 0, 0, -k, x, 0)))
        x += g.width * k
    return pen.getCommands(), x


# Defaults live on the root as presentation attributes so per-element fill/font-size
# attributes still win (a CSS `text{fill:..}` rule would override them).
SVG_OPEN = ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            'role="img" aria-label="{label}" fill="' + C["muted"] + '" font-size="12">')


def _style(css, extra=""):
    return f"<style>{css}text{{font-family:pm,{FALLBACK}}}{extra}</style>"


def _frame(w, h):
    return f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="8" fill="{C["panel"]}" stroke="{C["line"]}"/>'


def status_mark(kind, x, y):
    cy = y - 4  # sits on the text's x-height
    if kind == "active":
        return f'<circle cx="{x + 4:.1f}" cy="{cy}" r="4" fill="{C["ok"]}"/>'
    if kind == "building":
        return (f'<circle cx="{x + 4:.1f}" cy="{cy}" r="3.5" fill="none" stroke="{C["amber"]}" stroke-width="1.5"/>'
                f'<path d="M{x + 4:.1f} {cy - 3.5}a3.5 3.5 0 0 1 0 7z" fill="{C["amber"]}"/>')
    if kind == "shipped":
        return (f'<path d="M{x:.1f} {cy}l3 3l5-6" fill="none" stroke="{C["text"]}" stroke-width="1.8" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
    raise ValueError(f"unknown status {kind!r}")


def days(n):
    return f"{n} day" if n == 1 else f"{n} days"


def icon_d(slug):
    root = ET.parse(ASSETS / "icons" / f"{slug}.svg").getroot()
    return root.find("{http://www.w3.org/2000/svg}path").get("d")


def render_header(c):
    w, h = 840, 260
    body = ["$ whoami", *c["lines"], *(t for _, t in c["status"])]
    css = font_face(c["prompt"] + "".join(body), "pm")
    name_d, name_w = name_path(c["name"], 40)
    if name_w > w - 64:
        raise ValueError(f"name is {name_w:.0f}px wide, max {w - 64}")
    anim = ("text,.l{opacity:0;animation:in .5s cubic-bezier(.22,1,.36,1) forwards}"
            ".bar text{opacity:1;animation:none}"
            "@keyframes in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}"
            ".cur{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
            "@media (prefers-reduced-motion:reduce){text,.l,.cur{animation:none;opacity:1}}")
    cw = char_w(14)

    def delay(i):
        return f' style="animation-delay:{i * 80}ms"'

    out = [SVG_OPEN.format(w=w, h=h, label=esc(f"{c['name'].title()}, {c['lines'][0]}")),
           _style(css, anim), _frame(w, h),
           f'<g class="bar"><circle cx="20" cy="18" r="5" fill="{C["line"]}"/><circle cx="36" cy="18" r="5" fill="{C["line"]}"/>'
           f'<circle cx="52" cy="18" r="5" fill="{C["line"]}"/><text x="72" y="22">{esc(c["prompt"])}</text></g>',
           f'<path d="M0 36.5H{w}" stroke="{C["line"]}"/>',
           f'<text x="32" y="76" font-size="14" fill="{C["amber"]}"{delay(0)}>$ whoami</text>',
           f'<g class="l"{delay(1)}><path transform="translate(32 124)" d="{name_d}" fill="{C["text"]}"/></g>',
           f'<text x="32" y="158" font-size="14"{delay(2)}>{esc(c["lines"][0])}</text>',
           f'<text x="32" y="182" font-size="14"{delay(3)}>{esc(c["lines"][1])}</text>']
    x = 32.0
    for kind, label in c["status"]:
        out.append(f'<g class="l"{delay(4)}>{status_mark(kind, x, 224)}</g>')
        out.append(f'<text x="{x + 16:.1f}" y="224" font-size="14" fill="{C["text"]}"{delay(4)}>{esc(label)}</text>')
        x += 16 + len(label) * cw + 28
    out.append(f'<g class="l"{delay(5)}><rect class="cur" x="{x - 18:.1f}" y="211" width="8" height="16" fill="{C["amber"]}"/></g>')
    out.append("</svg>")
    return "".join(out)


def render_card(p):
    w, h = 410, 170
    lines = textwrap.wrap(p["desc"], 42)
    if len(lines) > 3:
        raise ValueError(f"description for {p['name']} wraps to {len(lines)} lines, max 3")
    css = font_face(p["desc"] + p["lang"] + p["status"], "pm") + font_face(p["name"], "pb", wght=600)
    word = p["status"]
    chip_w = len(p["lang"]) * char_w(11) + 16
    out = [SVG_OPEN.format(w=w, h=h, label=esc(f"{p['name']}: {p['desc']} {p['lang']}, {word}")),
           _style(css), _frame(w, h),
           f'<text x="20" y="38" font-size="16" fill="{C["text"]}" style="font-family:pb,{FALLBACK}">{esc(p["name"])}</text>']
    for i, line in enumerate(lines):
        out.append(f'<text x="20" y="{66 + i * 18}">{esc(line)}</text>')
    out += [f'<rect x="20.5" y="131.5" width="{chip_w:.1f}" height="21" rx="4" fill="none" stroke="{C["line"]}"/>',
            f'<text x="28" y="146" font-size="11">{esc(p["lang"])}</text>',
            status_mark(p["status"], 20 + chip_w + 14, 146),
            f'<text x="{20 + chip_w + 30:.1f}" y="146" font-size="11">{esc(word)}</text>', "</svg>"]
    return "".join(out)


def render_stack(rows):
    w, h = 840, 150
    labels = "".join(name for _, items in rows for _, name in items) + "".join(r for r, _ in rows)
    css = font_face(labels, "pm")
    out = [SVG_OPEN.format(w=w, h=h, label=esc("Stack. " + " ".join(
        f"{r}: {', '.join(n for _, n in items)}." for r, items in rows))), _style(css), _frame(w, h)]
    for row, (label, items) in enumerate(rows):
        top = 22 + row * 66
        out.append(f'<text x="24" y="{top + 17}" fill="{C["amber"]}">{esc(label)}</text>')
        cell = (w - 120) / 8
        for i, (slug, name) in enumerate(items):
            cx = 100 + cell * i + cell / 2
            out.append(f'<path transform="translate({cx - 12:.1f} {top})" d="{icon_d(slug)}" fill="{C["muted"]}"/>')
            out.append(f'<text x="{cx:.1f}" y="{top + 42}" font-size="11" text-anchor="middle">{esc(name)}</text>')
    out.append("</svg>")
    return "".join(out)


def render_stats(s):
    w, h = 840, 200
    metrics = [(f"{s['total']:,}", "contributions, last year"), (days(s["current"]), "current streak"),
               (days(s["longest"]), "longest streak"), (str(s["repos"]), "public repos")]
    langs = s["langs"]
    text = ("".join(a + b for a, b in metrics) + "".join(f"{n}{p}%" for n, p in langs)
            + "top languagesno language dataupdated " + s["updated"])
    css = font_face(text, "pm")
    out = [SVG_OPEN.format(w=w, h=h, label=esc(
        f"{s['total']} contributions in the last year, current streak {days(s['current'])}, "
        f"longest {days(s['longest'])}, {s['repos']} public repos")),
        _style(css, ".v{font-size:28px;fill:" + C["text"] + ";font-variant-numeric:tabular-nums}"), _frame(w, h)]
    for i, (value, label) in enumerate(metrics):
        x, y = 32 + (i % 2) * 190, 64 + (i // 2) * 72
        out.append(f'<text class="v" x="{x}" y="{y}">{esc(value)}</text><text x="{x}" y="{y + 20}">{esc(label)}</text>')
    out.append('<text x="440" y="40">top languages</text>')
    if not langs:
        out.append('<text x="440" y="72">no language data</text>')
    shades = [1, .72, .5, .34, .22]
    x, bar_w = 440.0, 368
    for i, (name, pct) in enumerate(langs):
        seg = bar_w * pct / 100
        out.append(f'<rect x="{x:.1f}" y="52" width="{max(seg - 2, 1):.1f}" height="10" rx="2" '
                   f'fill="{C["amber"]}" fill-opacity="{shades[i]}"/>')
        x += seg
        y = 92 + i * 20
        out.append(f'<rect x="440" y="{y - 9}" width="10" height="10" rx="2" fill="{C["amber"]}" fill-opacity="{shades[i]}"/>'
                   f'<text x="458" y="{y}" fill="{C["text"]}">{esc(name)}</text>'
                   f'<text x="808" y="{y}" text-anchor="end">{pct}%</text>')
    out.append(f'<text x="808" y="188" font-size="11" text-anchor="end">updated {esc(s["updated"])}</text></svg>')
    return "".join(out)
