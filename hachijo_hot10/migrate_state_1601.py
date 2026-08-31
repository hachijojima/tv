#!/usr/bin/env python3
"""Adopt the final 1601-track master without changing live chart state.

Only the 12 appended track-state entries are added to the production state.  The
future projection is generated from an in-memory copy, so ``latest.json`` and
the current chart-day JSON remain untouched until the regular 03:05 JST job.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import hot10


OLD_TRACK_COUNT = 1589
FINAL_TRACK_COUNT = 1601


def migrate_state(before: dict[str, Any]) -> dict[str, Any]:
    """Return a migrated copy, preserving every existing state value exactly."""
    after = copy.deepcopy(before)
    tracks = after.get("tracks")
    if not isinstance(tracks, dict) or set(tracks) != {str(value) for value in range(1, OLD_TRACK_COUNT + 1)}:
        raise ValueError("production state must contain exactly track IDs 1..1589 before migration")
    for track_id in range(OLD_TRACK_COUNT + 1, FINAL_TRACK_COUNT + 1):
        tracks[str(track_id)] = hot10.blank_track_state()
    return after


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_future_projection(
    state: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any], current_day: date, horizon_end: date
) -> int:
    """Replace only dates after ``current_day`` using a private projected state."""
    projected = copy.deepcopy(state)
    # Advance the private state across today's pending daily generation.  This
    # mirrors tomorrow's normal ``today`` run while keeping today's live files
    # and the production state entirely untouched.
    hot10.generate_chart(current_day, tracks, projected, config, random.Random(int(current_day.strftime("%Y%m%d"))))
    count = 0
    day = current_day + timedelta(days=1)
    while day <= horizon_end:
        chart = hot10.generate_chart(day, tracks, projected, config, random.Random(int(day.strftime("%Y%m%d"))))
        generated_at = datetime(
            day.year, day.month, day.day, config["chart_boundary_hour"], tzinfo=ZoneInfo(config["timezone"])
        ).isoformat()
        hot10.atomic_write_json(
            hot10.OUTPUT_DIR / f"{day.isoformat()}.json",
            {"date": chart["date"], "generated_at": generated_at, "chart": chart["chart"]},
        )
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
    original_bytes = hot10.STATE_PATH.read_bytes()
    before = json.loads(original_bytes)
    after = migrate_state(before)
    if before["tracks"] != {key: after["tracks"][key] for key in before["tracks"]}:
        raise AssertionError("existing production track state changed")
    if {key: value for key, value in before.items() if key != "tracks"} != {key: value for key, value in after.items() if key != "tracks"}:
        raise AssertionError("production globals changed")
    hot10.atomic_write_json(hot10.STATE_PATH, after)
    print(f"state migrated: 1589 -> {len(after['tracks'])} tracks")
    print(f"future projections regenerated: {write_future_projection(after, tracks, config, args.current_chart_date, args.horizon_end)}")


if __name__ == "__main__":
    main()
