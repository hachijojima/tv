#!/usr/bin/env python3
"""Adopt final 1728 master without changing protected live/current HOT10 data."""

from __future__ import annotations

import argparse
import copy
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import hot10


OLD_TRACK_COUNT = 1726
FINAL_TRACK_COUNT = 1728


def migrate_state(before: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Keep every 1726C track/global state; append only standard initial states."""
    after = copy.deepcopy(before)
    previous = after.get("tracks")
    old_ids = {str(value) for value in range(1, OLD_TRACK_COUNT + 1)}
    final_ids = {str(value) for value in range(1, FINAL_TRACK_COUNT + 1)}
    if not isinstance(previous, dict) or set(previous) != old_ids:
        raise ValueError("production state must contain exactly track IDs 1..1726")
    clean = hot10.initial_state(tracks, config)["tracks"]
    for track_id in range(OLD_TRACK_COUNT + 1, FINAL_TRACK_COUNT + 1):
        previous[str(track_id)] = copy.deepcopy(clean[str(track_id)])
    if set(previous) != final_ids:
        raise AssertionError("final state IDs are not continuous 1..1728")
    return after


def audit(before: dict[str, Any], after: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any]) -> None:
    clean = hot10.initial_state(tracks, config)["tracks"]
    if {key: value for key, value in before.items() if key != "tracks"} != {key: value for key, value in after.items() if key != "tracks"}:
        raise AssertionError("global state changed")
    if any(before["tracks"][str(track_id)] != after["tracks"][str(track_id)] for track_id in range(1, OLD_TRACK_COUNT + 1)):
        raise AssertionError("an existing 1726C track state changed")
    if any(after["tracks"][str(track_id)] != clean[str(track_id)] for track_id in range(OLD_TRACK_COUNT + 1, FINAL_TRACK_COUNT + 1)):
        raise AssertionError("a new track is not at the standard initial state")


def write_future_projection(state: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any], current_day: date, horizon_end: date) -> int:
    projected = copy.deepcopy(state)
    if date.fromisoformat(projected["last_generated_chart_date"]) != current_day:
        raise ValueError("production state date must equal protected current chart date")
    count = 0
    for offset in range(1, (horizon_end - current_day).days + 1):
        day = current_day + timedelta(days=offset)
        chart = hot10.generate_chart(day, tracks, projected, config, random.Random(int(day.strftime("%Y%m%d"))))
        generated_at = datetime(day.year, day.month, day.day, config["chart_boundary_hour"], tzinfo=ZoneInfo(config["timezone"])).isoformat()
        hot10.atomic_write_json(hot10.OUTPUT_DIR / f"{day.isoformat()}.json", {"date": chart["date"], "generated_at": generated_at, "chart": chart["chart"]})
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-chart-date", required=True, type=date.fromisoformat)
    parser.add_argument("--horizon-end", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    config = hot10.load_config()
    tracks = hot10.load_tracks(hot10.resolve_master_path(config), FINAL_TRACK_COUNT)
    before = json.loads(hot10.STATE_PATH.read_text(encoding="utf-8"))
    after = migrate_state(before, tracks, config)
    audit(before, after, tracks, config)
    hot10.atomic_write_json(hot10.STATE_PATH, after)
    count = write_future_projection(after, tracks, config, args.current_chart_date, args.horizon_end)
    print(f"state migrated: preserved=1726 reset=0 added=2; future projections regenerated={count}")


if __name__ == "__main__":
    main()
