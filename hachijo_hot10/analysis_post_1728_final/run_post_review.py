#!/usr/bin/env python3
"""Read-only 365-day post-adoption observation for final 1728 HOT10."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import hot10
SEEDS = (20260826, 12345, 20260901, 777, 424242)
CANONICAL_SEED = 20260826
START = date(2026, 8, 26)
FOCUS = ("いまみれん", "Fishmans", "フジファブリック", "ゆらゆら帝国", "パスピエ")
BASELINE_1726_SLOTS = {"いまみれん": 1, "Fishmans": 7, "フジファブリック": 4, "ゆらゆら帝国": 2, "パスピエ": 0}


def rows(charts):
    return [row for chart in charts for row in chart["chart"]]


def max_run(values):
    return max(values, default=0)


def metrics(charts):
    flat = rows(charts)
    daily = [{row["track_id"] for row in chart["chart"]} for chart in charts]
    replacements = [10 - len(left & right) for left, right in zip(daily, daily[1:])]
    artist_counts = Counter(row["artist"] for row in flat)
    track_counts = Counter(row["track_id"] for row in flat)
    total = len(flat)
    return {
        "days": len(charts),
        "overall_replacements_per_day": sum(replacements) / len(replacements),
        "retention_per_day": 10 - sum(replacements) / len(replacements),
        "ever_appeared_tracks": len(track_counts),
        "artist_hhi": sum((count / total) ** 2 for count in artist_counts.values()),
        "longest_number_1_streak": max_run(row["days_at_number_1"] for row in flat),
        "longest_top10_streak": max_run(row["top10_streak"] for row in flat),
        "top10_concentration": max(track_counts.values()) / total,
        "top25_concentration": sum(count for _, count in track_counts.most_common(25)) / total,
        "top50_concentration": sum(count for _, count in track_counts.most_common(50)) / total,
        "top100_concentration": sum(count for _, count in track_counts.most_common(100)) / total,
    }


def canonical_reports(charts):
    flat = rows(charts)
    artist_rows, per_track, top50, artist_top30 = [], [], [], []
    for artist in FOCUS:
        artist_entries = [row for row in flat if row["artist"] == artist]
        tracks = Counter(row["track_id"] for row in artist_entries)
        artist_rows.append({
            "artist": artist, "baseline_1726_slots": BASELINE_1726_SLOTS[artist],
            "total_top10_slots": len(artist_entries),
            "appearance_days": len({chart["date"] for chart in charts if any(row["artist"] == artist for row in chart["chart"])}),
            "number_1_days": sum(row["rank"] == 1 for row in artist_entries),
            "reentry_total": sum(row["movement"] == "RE" for row in artist_entries),
            "appeared_track_count": len(tracks),
            "longest_top10_streak": max_run(row["top10_streak"] for row in artist_entries),
        })
        for track_id, count in tracks.items():
            entries = [row for row in artist_entries if row["track_id"] == track_id]
            one = entries[0]
            per_track.append({"artist": artist, "track_id": track_id, "title": one["title"], "top10_days": count, "number_1_days": sum(row["rank"] == 1 for row in entries), "reentry_total": sum(row["movement"] == "RE" for row in entries), "longest_top10_streak": max_run(row["top10_streak"] for row in entries)})
    track_counts = Counter(row["track_id"] for row in flat)
    samples = {row["track_id"]: row for row in flat}
    for track_id, count in track_counts.most_common(50):
        row = samples[track_id]
        top50.append({"rank": len(top50) + 1, "track_id": track_id, "artist": row["artist"], "title": row["title"], "top10_days": count})
    for artist, count in Counter(row["artist"] for row in flat).most_common(30):
        artist_top30.append({"rank": len(artist_top30) + 1, "artist": artist, "top10_slots": count})
    return artist_rows, sorted(per_track, key=lambda row: (FOCUS.index(row["artist"]), -row["top10_days"], row["track_id"])), top50, artist_top30


def write_csv(path, fieldnames, data):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader(); writer.writerows(data)


def main():
    config = hot10.load_config(); tracks = hot10.load_tracks(hot10.resolve_master_path(config), 1728)
    runs = {seed: hot10.simulate(365, seed, tracks, config, START) for seed in SEEDS}
    summaries = [{"seed": seed, **metrics(charts)} for seed, charts in runs.items()]
    canonical = runs[CANONICAL_SEED]
    focus, per_track, top50, artist_top30 = canonical_reports(canonical)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "seed_summary.csv", list(summaries[0]), summaries)
    write_csv(OUT / "artist_focus.csv", list(focus[0]), focus)
    write_csv(OUT / "per_track.csv", list(per_track[0]), per_track)
    write_csv(OUT / "top50_appearances.csv", list(top50[0]), top50)
    write_csv(OUT / "artist_slots_top30.csv", list(artist_top30[0]), artist_top30)
    payload = {"canonical_seed": CANONICAL_SEED, "start_date": START.isoformat(), "master": hot10.resolve_master_path(config).name, "seed_summaries": summaries, "canonical_focus_artists": focus, "canonical_artist_slots_top30": artist_top30}
    (OUT / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    canonical_summary = summaries[0]
    lines = ["# 1728 Final Post-adoption Review", "", "Read-only observation only. No rollback, retune, or A/B decision is made from these results.", "", "## Canonical (seed 20260826; 365 days)", ""]
    for key, value in canonical_summary.items():
        if key != "seed": lines.append(f"- {key}: {value}")
    lines += ["", "## Focus artists (canonical)", "", "| artist | 1726 baseline slots | final slots | appearance days | #1 days | RE | tracks | longest Top10 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    lines += [f"| {row['artist']} | {row['baseline_1726_slots']} | {row['total_top10_slots']} | {row['appearance_days']} | {row['number_1_days']} | {row['reentry_total']} | {row['appeared_track_count']} | {row['longest_top10_streak']} |" for row in focus]
    lines += ["", "See `results.json`, `seed_summary.csv`, `artist_focus.csv`, `per_track.csv`, `top50_appearances.csv`, and `artist_slots_top30.csv` for full data."]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
