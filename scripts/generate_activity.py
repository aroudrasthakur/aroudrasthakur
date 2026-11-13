#!/usr/bin/env python3
"""Generate assets/contribution-activity.svg from a GitHub user's contribution calendar.

Uses only the Python standard library. Run in GitHub Actions with GITHUB_TOKEN set.
Environment variables:
  GITHUB_TOKEN  token for the GitHub GraphQL API (required unless --sample is used)
  GITHUB_USER   GitHub username (default: aroudrasthakur)
"""
import datetime
import json
import os
import sys
import urllib.request

USER = os.environ.get("GITHUB_USER", "aroudrasthakur")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "contribution-activity.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "contribution-graph-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        raise RuntimeError("GitHub API error: " + json.dumps(payload)[:500])
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = []
    for week in cal["weeks"]:
        days = week["contributionDays"]
        if not days:
            continue
        weeks.append((days[0]["date"], sum(d["contributionCount"] for d in days)))
    return weeks, cal["totalContributions"]


def nice_max(value):
    if value <= 5:
        return 5
    step = 5 if value <= 30 else 10 if value <= 100 else 25
    return ((value + step - 1) // step) * step


def render_svg(weeks, total, login):
    width, height = 830, 200
    left, right, top, bottom = 44, 16, 40, 28
    plot_w, plot_h = width - left - right, height - top - bottom
    counts = [c for _, c in weeks]
    y_max = nice_max(max(counts) if counts else 0)
    n = max(len(weeks) - 1, 1)

    def x(i):
        return left + plot_w * i / n

    def y(v):
        return top + plot_h * (1 - v / y_max)

    points = [(x(i), y(c)) for i, c in enumerate(counts)]
    line = " ".join("%.1f,%.1f" % p for p in points)
    area = "M%.1f,%.1f L%s L%.1f,%.1f Z" % (
        left, top + plot_h, " L".join("%.1f,%.1f" % p for p in points), x(len(points) - 1), top + plot_h)

    grid = []
    for k in range(5):
        v = y_max * k / 4
        yy = y(v)
        grid.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#30363d" stroke-width="1" stroke-dasharray="3 4"/>'
                    % (left, yy, width - right, yy))
        grid.append('<text x="%d" y="%.1f" fill="#8b949e" font-size="11" text-anchor="end">%d</text>'
                    % (left - 8, yy + 4, round(v)))

    months, last_month = [], None
    for i, (date_str, _) in enumerate(weeks):
        month = datetime.date.fromisoformat(date_str).strftime("%b")
        if month != last_month:
            months.append('<text x="%.1f" y="%d" fill="#8b949e" font-size="11">%s</text>' % (x(i), height - 8, month))
            last_month = month

    title = "%s contributions in the last year" % format(total, ",")
    return """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{title}" font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif">
  <defs>
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#6366f1" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#22d3ee" stop-opacity="0.02"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" rx="8" fill="#0d1117"/>
  <text x="{left}" y="24" fill="#e6edf3" font-size="14" font-weight="600">{title}</text>
  {grid}
  <path d="{area}" fill="url(#fill)"/>
  <polyline points="{line}" fill="none" stroke="#6366f1" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
  {months}
</svg>
""".format(w=width, h=height, left=left, title=title, grid="\n  ".join(grid),
           area=area, line=line, months="\n  ".join(months))


def main():
    if "--sample" in sys.argv:
        import random
        random.seed(1)
        start = datetime.date(2025, 11, 9)
        weeks = [((start + datetime.timedelta(weeks=i)).isoformat(), random.randint(0, 40)) for i in range(53)]
        total = sum(c for _, c in weeks)
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("GITHUB_TOKEN is not set")
        weeks, total = fetch(USER, token)
    svg = render_svg(weeks, total, USER)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote", os.path.normpath(OUT), "-", total, "contributions")


if __name__ == "__main__":
    main()
