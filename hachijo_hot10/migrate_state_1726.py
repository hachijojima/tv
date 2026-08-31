#!/usr/bin/env python3
"""Adopt 1726C without changing the live/current HACHIJO HOT 10 chart."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import hot10


OLD_TRACK_COUNT = 1601
FINAL_TRACK_COUNT = 1726
RESET_PATH = hot10.ROOT / "HACHIJO_HOT10_replaced47_state_reset.csv"


def replacement_ids(path: Path = RESET_PATH) -> set[int]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = {int(row["track_id"]) for row in rows}
    if len(rows) != 47 or len(ids) != 47:
        raise ValueError("replacement reset file must contain exactly 47 unique IDs")
    if any(row["state_policy"] != "RESET_TO_STANDARD_INITIAL_TRACK_STATE" for row in rows):
        raise ValueError("replacement reset file has an invalid state policy")
    return ids


def migrate_state(before: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any], reset_ids: set[int]) -> dict[str, Any]:
    """Preserve globals/unchanged tracks; reset identity changes and append new tracks."""
    after = copy.deepcopy(before)
    previous = after.get("tracks")
    if not isinstance(previous, dict):
        raise ValueError("production state must contain a tracks map")
    old_ids = {str(value) for value in range(1, OLD_TRACK_COUNT + 1)}
    final_ids = {str(value) for value in range(1, FINAL_TRACK_COUNT + 1)}
    if set(previous) == final_ids:
        return after
    if set(previous) != old_ids:
        raise ValueError("production state must contain track IDs 1..1601 or 1..1726")
    if len(reset_ids) != 47 or not reset_ids <= set(range(1, OLD_TRACK_COUNT + 1)):
        raise ValueError("invalid replacement ID set")
    clean = hot10.initial_state(tracks, config)["tracks"]
    for track_id in reset_ids | set(range(OLD_TRACK_COUNT + 1, FINAL_TRACK_COUNT + 1)):
        previous[str(track_id)] = copy.deepcopy(clean[str(track_id)])
    return after


def audit(before: dict[str, Any], after: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any], reset_ids: set[int]) -> None:
    preserved = set(range(1, OLD_TRACK_COUNT + 1)) - reset_ids
    clean = hot10.initial_state(tracks, config)["tracks"]
    if len(preserved) != 1554 or len(reset_ids) != 47:
        raise AssertionError("unexpected state migration group sizes")
    if {key: value for key, value in before.items() if key != "tracks"} != {key: value for key, value in after.items() if key != "tracks"}:
        raise AssertionError("global state changed")
    if any(before["tracks"][str(track_id)] != after["tracks"][str(track_id)] for track_id in preserved):
        raise AssertionError("an unchanged existing track state changed")
    changed = reset_ids | set(range(OLD_TRACK_COUNT + 1, FINAL_TRACK_COUNT + 1))
    if any(after["tracks"][str(track_id)] != clean[str(track_id)] for track_id in changed):
        raise AssertionError("a reset/new track is not at the standard initial state")
    if set(after["tracks"]) != {str(value) for value in range(1, FINAL_TRACK_COUNT + 1)}:
        raise AssertionError("final state ID set is not 1..1726")


def write_future_projection(state: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any], current_day: date, horizon_end: date) -> int:
    projected = copy.deepcopy(state)
    last_generated = date.fromisoformat(projected["last_generated_chart_date"])
    if last_generated > current_day:
        raise ValueError("production state is newer than the protected current chart date")
    if last_generated < current_day:
        hot10.generate_chart(current_day, tracks, projected, config, random.Random(int(current_day.strftime("%Y%m%d"))))
    count = 0
    day = current_day + timedelta(days=1)
    while day <= horizon_end:
        chart = hot10.generate_chart(day, tracks, projected, config, random.Random(int(day.strftime("%Y%m%d"))))
        generated_at = datetime(day.year, day.month, day.day, config["chart_boundary_hour"], tzinfo=ZoneInfo(config["timezone"])).isoformat()
        hot10.atomic_write_json(hot10.OUTPUT_DIR / f"{day.isoformat()}.json", {"date": chart["date"], "generated_at": generated_at, "chart": chart["chart"]})
        count += 1
        day += timedelta(days=1)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-chart-date", required=True, type=date.fromisoformat)
    parser.add_argument("--horizon-end", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    if args.horizon_end <= args.current_chart_date:
        raise ValueError("horizon end must be after current chart date")
    config = hot10.load_config()
    tracks = hot10.load_tracks(hot10.resolve_master_path(config), FINAL_TRACK_COUNT)
    before = json.loads(hot10.STATE_PATH.read_text(encoding="utf-8"))
    reset_ids = replacement_ids()
    after = migrate_state(before, tracks, config, reset_ids)
    audit(before, after, tracks, config, reset_ids)
    hot10.atomic_write_json(hot10.STATE_PATH, after)
    count = write_future_projection(after, tracks, config, args.current_chart_date, args.horizon_end)
    print(f"state migrated: preserved=1554 reset=47 added=125; future projections regenerated={count}")


if __name__ == "__main__":
    main()
