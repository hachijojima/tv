#!/usr/bin/env python3
"""Export dated HACHIJO HOT 10 JSON files to a readable local HTML report."""

from __future__ import annotations

import argparse
import html
import json
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def render_row(item: dict) -> str:
    return (
        "<tr>"
        f"<td class=\"rank\">{int(item['rank']):02d}</td>"
        f"<td><strong>{html.escape(item.get('artist', '—'))}</strong>"
        f"<span>{html.escape(item.get('title', '—'))}</span></td>"
        f"<td class=\"movement\">{html.escape(item.get('movement', '—'))}</td>"
        "</tr>"
    )


def render_day(day: date, payload: dict) -> str:
    chart = payload.get("chart", [])
    if len(chart) != 10:
        raise ValueError(f"{day}: expected 10 chart entries, found {len(chart)}")
    rows = "".join(render_row(item) for item in chart)
    return (
        f'<section id="d-{day.isoformat()}"><h2>{day.isoformat()}</h2>'
        "<table><thead><tr><th>Rank</th><th>Artist / Title</th><th>Move</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></section>"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.days < 1:
        raise ValueError("--days must be at least 1")

    sections = []
    for offset in range(args.days):
        chart_day = args.start + timedelta(days=offset)
        path = ROOT / "hot10_output" / f"{chart_day.isoformat()}.json"
        with path.open(encoding="utf-8") as source:
            payload = json.load(source)
        if payload.get("date") != chart_day.isoformat():
            raise ValueError(f"{path}: date does not match filename")
        sections.append(render_day(chart_day, payload))

    end = args.start + timedelta(days=args.days - 1)
    nav_links = "".join(
        f'<a href="#d-{(args.start + timedelta(days=offset)).isoformat()}">'
        f'{(args.start + timedelta(days=offset)).strftime("%m/%d")}</a>'
        for offset in range(args.days)
    )
    document = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HACHIJO HOT 10 — {args.start} to {end}</title>
<style>
:root{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172033;background:#f4f7fb}}
body{{margin:0;padding:32px 18px 56px}}main{{max-width:760px;margin:auto}}h1{{margin:0;font-size:clamp(24px,4vw,34px)}}p{{color:#5b677a;font-size:14px;margin:8px 0 20px}}nav{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 24px}}nav a{{padding:5px 8px;border:1px solid #dce3ee;border-radius:6px;background:#fff;color:#334155;font-size:11px;text-decoration:none}}section{{margin:18px 0;background:#fff;border:1px solid #dce3ee;border-radius:14px;overflow:hidden;scroll-margin-top:12px}}h2{{margin:0;padding:14px 18px;font-size:16px;background:#f8faff;border-bottom:1px solid #dce3ee}}table{{width:100%;border-collapse:collapse;table-layout:fixed}}th,td{{padding:10px 14px;text-align:left;vertical-align:top;border-bottom:1px solid #edf0f5}}tr:last-child td{{border:0}}th{{color:#52617a;font-size:12px}}th:first-child,td:first-child{{width:58px;text-align:center}}th:last-child,td:last-child{{width:64px;text-align:right}}strong,span{{display:block}}strong{{font-size:14px}}span{{margin-top:3px;color:#48566d;font-size:13px}}.rank{{font-variant-numeric:tabular-nums;font-weight:700}}.movement{{font-size:13px;font-weight:700;white-space:nowrap}}@media(max-width:560px){{body{{padding:18px 10px 40px}}th,td{{padding:10px 8px}}strong{{font-size:13px}}span{{font-size:12px}}}}
</style></head><body><main>
<h1>HACHIJO HOT 10</h1>
<p>{args.start.isoformat()} 〜 {end.isoformat()} · 日別TOP 10</p>
<nav>{nav_links}</nav>
{''.join(sections)}
</main></body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
