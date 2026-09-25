"""Build the profile README SVGs into assets/. Run: python scripts/build.py"""
import json
import os
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

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
