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
    day_weeks = []
    for week in cal["weeks"]:
        days = [(d["date"], d["contributionCount"]) for d in week["contributionDays"]]
        if days:
            day_weeks.append(days)
    return day_weeks, cal["totalContributions"]


def weekly_totals(day_weeks):
    return [(days[0][0], sum(c for _, c in days)) for days in day_weeks]


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


HEAT_COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def heat_level(count, thresholds):
    if count <= 0:
        return 0
    for level, limit in enumerate(thresholds, start=1):
        if count <= limit:
            return level
    return 4


def render_heatmap(day_weeks, total):
    """GitHub-style calendar: columns are weeks (Sun-Sat rows), colored by daily count."""
    cell, gap = 11, 3
    step = cell + gap
    left, top = 36, 58
    width = left + step * len(day_weeks) + 16
    height = top + step * 7 + 40

    nonzero = sorted(c for week in day_weeks for _, c in week if c > 0)
    if nonzero:
        q = lambda f: nonzero[min(len(nonzero) - 1, int(len(nonzero) * f))]
        thresholds = [q(0.25), q(0.5), q(0.75)]
    else:
        thresholds = [1, 2, 3]

    rects, months, last_month = [], [], None
    for col, days in enumerate(day_weeks):
        first = datetime.date.fromisoformat(days[0][0])
        month = first.strftime("%b")
        if month != last_month and (col == 0 or first.day <= 7):
            months.append('<text x="%d" y="%d" fill="#8b949e" font-size="11">%s</text>' % (left + col * step, top - 10, month))
            last_month = month
        for date_str, count in days:
            d = datetime.date.fromisoformat(date_str)
            row = (d.weekday() + 1) % 7  # Sunday = 0
            rects.append('<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s" stroke="#ffffff" stroke-opacity="0.06"><title>%s: %d contribution%s</title></rect>'
                         % (left + col * step, top + row * step, cell, cell,
                            HEAT_COLORS[heat_level(count, thresholds)], date_str, count, "" if count == 1 else "s"))

    labels = "".join('<text x="%d" y="%d" fill="#8b949e" font-size="10" text-anchor="end">%s</text>'
                     % (left - 8, top + row * step + 10, name) for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")))

    ly = top + 7 * step + 14
    legend_x = width - 16 - (5 * step + 70)
    legend = ['<text x="%d" y="%d" fill="#8b949e" font-size="10">Less</text>' % (legend_x, ly + 9)]
    for i, color in enumerate(HEAT_COLORS):
        legend.append('<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s" stroke="#ffffff" stroke-opacity="0.06"/>'
                      % (legend_x + 28 + i * step, ly, cell, cell, color))
    legend.append('<text x="%d" y="%d" fill="#8b949e" font-size="10">More</text>' % (legend_x + 28 + 5 * step + 4, ly + 9))

    title = "%s contributions in the last year" % format(total, ",")
    return """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{title}" font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif">
  <rect width="{w}" height="{h}" rx="8" fill="#0d1117"/>
  <text x="{left}" y="24" fill="#e6edf3" font-size="14" font-weight="600">{title}</text>
  {months}
  {labels}
  {rects}
  {legend}
</svg>
""".format(w=width, h=height, left=left, title=title, months="\n  ".join(months),
           labels=labels, rects="\n  ".join(rects), legend="\n  ".join(legend))


def main():
    out_dir = os.environ.get("ASSETS_DIR") or os.path.dirname(OUT)
    if "--sample" in sys.argv:
        import random
        random.seed(1)
        start = datetime.date(2025, 11, 16)  # a Sunday
        day_weeks = []
        for w in range(53):
            week = []
            for d in range(7):
                date = start + datetime.timedelta(weeks=w, days=d)
                if date <= datetime.date(2026, 11, 18):
                    week.append((date.isoformat(), random.choice([0, 0, 0, 1, 2, 3, 5, 8, 12])))
            if week:
                day_weeks.append(week)
        total = sum(c for wk in day_weeks for _, c in wk)
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("GITHUB_TOKEN is not set")
        day_weeks, total = fetch(USER, token)
    os.makedirs(out_dir, exist_ok=True)
    outputs = {
        "contribution-activity.svg": render_svg(weekly_totals(day_weeks), total, USER),
        "contribution-heatmap.svg": render_heatmap(day_weeks, total),
    }
    for name, svg in outputs.items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print("Wrote", os.path.normpath(path), "-", total, "contributions")


if __name__ == "__main__":
    main()
