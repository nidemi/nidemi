"""Build generated/top-langs.svg from every repo you own, private ones included.

Only language byte counts are read (Metadata permission); no code or repo
names end up in the image.
"""
import html
import json
import os
import urllib.request

TOKEN = os.environ["GH_TOKEN"]
COUNT = int(os.environ.get("LANGS_COUNT", "8"))
EXCLUDE = {s.strip().lower() for s in os.environ.get("EXCLUDE_LANGS", "").split(",") if s.strip()}
OUTPUT = os.environ.get("OUTPUT", "generated/top-langs.svg")

QUERY = """
query($cursor: String) {
  viewer {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes { languages(first: 100) { edges { size node { name color } } } }
    }
  }
}"""


def graphql(variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]["viewer"]["repositories"]


def collect():
    sizes, colors, cursor, repos = {}, {}, None, 0
    while True:
        page = graphql({"cursor": cursor})
        for repo in page["nodes"]:
            repos += 1
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                if name.lower() in EXCLUDE:
                    continue
                sizes[name] = sizes.get(name, 0) + edge["size"]
                colors[name] = edge["node"]["color"] or "#8b949e"
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    print(f"Scanned {repos} repos, {len(sizes)} languages")
    return sizes, colors


def render(sizes, colors):
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)
    items = [(n, s / total * 100, colors[n]) for n, s in ranked[:COUNT]]
    other = sum(s for _, s in ranked[COUNT:])
    if other:
        items.append(("Other", other / total * 100, "#8b949e"))

    width, pad = 350, 25
    bar_w = width - 2 * pad
    rows = (len(items) + 1) // 2
    height = 90 + rows * 22

    segments, x = [], float(pad)
    for _, pct, color in items:
        w = bar_w * pct / 100
        segments.append(f'<rect x="{x:.2f}" y="50" width="{w + 0.5:.2f}" height="8" fill="{color}"/>')
        x += w

    labels = []
    for i, (name, pct, color) in enumerate(items):
        cx = pad + (i % 2) * (bar_w / 2)
        cy = 85 + (i // 2) * 22
        labels.append(
            f'<circle cx="{cx + 5:.1f}" cy="{cy - 4}" r="5" fill="{color}"/>'
            f'<text x="{cx + 16:.1f}" y="{cy}" class="lang">{html.escape(name)} '
            f'<tspan class="pct">{pct:.1f}%</tspan></text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Most used languages">
<style>
.bg{{fill:#fffefe;stroke:#e4e2e2}}
.title{{font:600 18px 'Segoe UI',Ubuntu,'Helvetica Neue',Sans-Serif;fill:#2f80ed}}
.lang{{font:400 12px 'Segoe UI',Ubuntu,'Helvetica Neue',Sans-Serif;fill:#434d58}}
.pct{{fill:#6e7781}}
@media (prefers-color-scheme: dark){{
.bg{{fill:#0d1117;stroke:#30363d}}.title{{fill:#58a6ff}}.lang{{fill:#c9d1d9}}.pct{{fill:#8b949e}}
}}
</style>
<rect class="bg" x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="4.5"/>
<text x="{pad}" y="35" class="title">Most Used Languages</text>
<clipPath id="bar"><rect x="{pad}" y="50" width="{bar_w}" height="8" rx="4"/></clipPath>
<g clip-path="url(#bar)">{''.join(segments)}</g>
{''.join(labels)}
</svg>
"""


if __name__ == "__main__":
    svg = render(*collect())
    os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print(f"Wrote {OUTPUT}")
