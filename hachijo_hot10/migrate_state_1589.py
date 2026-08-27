#!/usr/bin/env python3
"""One-time additive state migration for the 1589-track MICROTUNE35 master."""

from __future__ import annotations

import copy
import json

import hot10


def main() -> None:
    tracks = hot10.load_tracks(hot10.resolve_master_path(hot10.load_config()))
    if len(tracks) != 1589:
        raise RuntimeError("MICROTUNE35 master is not active")
    before_bytes = hot10.STATE_PATH.read_bytes()
    before = json.loads(before_bytes)
    state = copy.deepcopy(before)
    existing = set(state.get("tracks", {}))
    required_existing = {str(track_id) for track_id in range(1, 1390)}
    additions = {str(track_id) for track_id in range(1390, 1590)}
    if existing != required_existing:
        raise RuntimeError("production state must contain exactly IDs 1..1389 before migration")
    state["tracks"].update({track_id: hot10.blank_track_state() for track_id in additions})
    if state["tracks"] != {**before["tracks"], **{track_id: hot10.blank_track_state() for track_id in additions}}:
        raise RuntimeError("state migration changed an existing track")
    if {key: value for key, value in state.items() if key != "tracks"} != {key: value for key, value in before.items() if key != "tracks"}:
        raise RuntimeError("state migration changed global state")
    hot10.atomic_write_json(hot10.STATE_PATH, state)
    after = json.loads(hot10.STATE_PATH.read_text(encoding="utf-8"))
    if {track_id: after["tracks"][track_id] for track_id in required_existing} != before["tracks"]:
        raise RuntimeError("existing state verification failed")
    if set(after["tracks"]) - existing != additions:
        raise RuntimeError("new track count verification failed")
    print("added=200 existing_1_1389_unchanged=yes global_state_unchanged=yes")


if __name__ == "__main__":
    main()
