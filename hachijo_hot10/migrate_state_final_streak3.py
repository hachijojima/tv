#!/usr/bin/env python3
"""Add FINAL streak-3 cooldown metadata without resetting live HOT10 state."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import hot10


def history_dates(output_dir: Path, through: date) -> list[Path]:
    paths = []
    for path in output_dir.glob("????-??-??.json"):
        try:
            if date.fromisoformat(path.stem) <= through:
                paths.append(path)
        except ValueError:
            continue
    return sorted(paths)


def migrate_state(before: dict[str, Any], tracks: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    """Preserve all existing values and derive only date metadata from chart history."""
    after = copy.deepcopy(before)
    last_generated = date.fromisoformat(after["last_generated_chart_date"])
    last_top10: dict[str, str] = {}
    artist_last_present: dict[str, str] = {}
    for path in history_dates(output_dir, last_generated):
        payload = json.loads(path.read_text(encoding="utf-8"))
        chart_day = date.fromisoformat(payload["date"])
        if chart_day > last_generated:
            raise ValueError(f"future chart included in migration: {path}")
        for row in payload["chart"]:
            track_id, artist = str(row["track_id"]), row["artist"]
            last_top10[track_id] = chart_day.isoformat()
            artist_last_present[artist] = chart_day.isoformat()
    artist_by_track = {str(track["track_id"]): track["artist"] for track in tracks}
    for track_id, item in after["tracks"].items():
        if item["ever_charted"]:
            last_top10.setdefault(track_id, (last_generated if item["last_rank"] is not None else last_generated - timedelta(days=item["days_outside_top10"])).isoformat())
        item["last_top10_date"] = last_top10.get(track_id)
        if item["last_top10_date"]:
            artist = artist_by_track[track_id]
            artist_last_present[artist] = max(artist_last_present.get(artist, ""), item["last_top10_date"])
    after["artist_last_present_date"] = artist_last_present
    return after


def audit(before: dict[str, Any], after: dict[str, Any]) -> None:
    for key, value in before.items():
        if key in ("tracks", "artist_last_present_date"):
            continue
        if after.get(key) != value:
            raise AssertionError(f"global state changed: {key}")
    for track_id, old_item in before["tracks"].items():
        new_item = after["tracks"].get(track_id)
        if new_item is None:
            raise AssertionError(f"track state removed: {track_id}")
        old_dynamic = {key: value for key, value in old_item.items() if key != "last_top10_date"}
        new_dynamic = {key: value for key, value in new_item.items() if key != "last_top10_date"}
        if new_dynamic != old_dynamic:
            raise AssertionError(f"track dynamic state changed: {track_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", type=Path, default=hot10.STATE_PATH)
    parser.add_argument("--output-dir", type=Path, default=hot10.OUTPUT_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    before = json.loads(args.state_file.read_text(encoding="utf-8"))
    tracks = hot10.load_tracks(hot10.resolve_master_path(hot10.load_config()))
    after = migrate_state(before, tracks, args.output_dir)
    audit(before, after)
    if args.write:
        hot10.atomic_write_json(args.state_file, after)
    print(f"state migration {'written' if args.write else 'validated'}: tracks={len(after['tracks'])} artists={len(after['artist_last_present_date'])}")


if __name__ == "__main__":
    main()
