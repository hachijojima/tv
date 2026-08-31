#!/usr/bin/env python3
"""HACHIJO HOT 10 production engine — F4.1-B."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import random
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "hot10_config.json"
STATE_PATH = ROOT / "hot10_state.json"
OUTPUT_DIR = ROOT / "hot10_output"
CSV_COLUMNS = (
    "track_id", "artist", "title", "base_strength", "emo", "popularity",
    "hachijo_fit", "oddity", "stickiness", "volatility", "enabled",
    "release_year", "freshness_bonus",
)
SCORE_COLUMNS = ("base_strength", "emo", "popularity", "hachijo_fit", "oddity", "stickiness", "volatility")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_master_path(config: dict[str, Any]) -> Path:
    path = Path(config["master_path"])
    return path if path.is_absolute() else ROOT / path


def load_tracks(path: Path, expected_count: int = 1601) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValueError("master CSV header does not match the F4.1-B schema")
        tracks: list[dict[str, Any]] = []
        for line, row in enumerate(reader, start=2):
            try:
                track = {
                    "track_id": int(row["track_id"]), "artist": row["artist"], "title": row["title"],
                    **{field: int(row[field]) for field in SCORE_COLUMNS}, "enabled": int(row["enabled"]),
                    "release_year": int(row["release_year"]) if row["release_year"] else None,
                    "freshness_bonus": float(row["freshness_bonus"] or 0),
                }
            except (TypeError, ValueError) as error:
                raise ValueError(f"line {line}: invalid numeric value") from error
            if not track["artist"] or not track["title"] or track["enabled"] not in (0, 1):
                raise ValueError(f"line {line}: invalid required field")
            if not all(0 <= track[field] <= 100 for field in SCORE_COLUMNS):
                raise ValueError(f"line {line}: score must be 0..100")
            tracks.append(track)
    expected_ids = set(range(1, expected_count + 1))
    if len(tracks) != expected_count or {track["track_id"] for track in tracks} != expected_ids:
        raise ValueError(f"master must contain unique track_id 1..{expected_count}")
    return tracks


def blank_track_state() -> dict[str, Any]:
    return {"heat": 0.0, "shock": 0.0, "top10_streak": 0, "number1_streak": 0,
            "days_outside_top10": 0, "ever_charted": False, "last_rank": None}


def initial_state(tracks: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    return {"version": config["version"], "last_generated_chart_date": None,
            "mood": {axis: 0.0 for axis in config["daily_mood"]["axes"]},
            "tracks": {str(track["track_id"]): blank_track_state() for track in tracks}}


def normalise_state(state: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("version", config["version"])
    state.setdefault("last_generated_chart_date", None)
    state.setdefault("mood", {})
    state.setdefault("tracks", {})
    for axis in config["daily_mood"]["axes"]:
        state["mood"].setdefault(axis, 0.0)
    for track in tracks:
        item = state["tracks"].setdefault(str(track["track_id"]), blank_track_state())
        for key, value in blank_track_state().items():
            item.setdefault(key, value)
    return state


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def effective_hachijo_fit(value: float, config: dict[str, Any]) -> float:
    rule = config["hachijo_fit_saturation"]
    return value if value <= rule["threshold"] else rule["threshold"] + (value - rule["threshold"]) * rule["above_threshold_multiplier"]


def static_score(track: dict[str, Any], config: dict[str, Any]) -> float:
    values = {**track, "hachijo_fit": effective_hachijo_fit(track["hachijo_fit"], config)}
    return sum(values[field] * weight for field, weight in config["static_score_weights"].items())


def effective_freshness(track: dict[str, Any], config: dict[str, Any]) -> float:
    rule = config["attenuated_freshness"]
    factor = clamp((rule["static_score_center"] - static_score(track, config)) / rule["divisor"], rule["minimum_factor"], rule["maximum_factor"])
    return track["freshness_bonus"] * factor


def update_daily_random_state(state: dict[str, Any], tracks: list[dict[str, Any]], config: dict[str, Any], rng: random.Random) -> None:
    mood_rule, heat_rule, shock_rule = config["daily_mood"], config["daily_heat"], config["wildcard_shock"]
    for axis in mood_rule["axes"]:
        state["mood"][axis] = mood_rule["persistence"] * state["mood"][axis] + rng.gauss(0, mood_rule["noise_sd"])
    for track in tracks:
        item = state["tracks"][str(track["track_id"])]
        item["heat"] = heat_rule["persistence"] * item["heat"] + rng.gauss(0, heat_rule["noise_sd_min"] + heat_rule["noise_sd_volatility_scale"] * track["volatility"] / 100)
        probability = shock_rule["base_probability"] + shock_rule["oddity_probability_scale"] * track["oddity"] / 100 + shock_rule["volatility_probability_scale"] * track["volatility"] / 100
        new_shock = rng.uniform(shock_rule["bonus_min"], shock_rule["bonus_max"]) if rng.random() < probability else 0.0
        item["shock"] = item["shock"] * shock_rule["decay_next_day"] + new_shock


def daily_score(track: dict[str, Any], state: dict[str, Any], config: dict[str, Any]) -> float:
    item = state["tracks"][str(track["track_id"])]
    score = static_score(track, config) + effective_freshness(track, config) + item["heat"] + item["shock"]
    mood = config["daily_mood"]
    score += sum(state["mood"][axis] * (track[axis] - 50) / mood["contribution_divisor"] for axis in mood["axes"])
    if item["last_rank"] is not None:
        inertia = config["previous_day_inertia"]
        score += inertia["base_bonus_for_rank_1"] - inertia["rank_step_down"] * (item["last_rank"] - 1) + inertia["stickiness_scale"] * (track["stickiness"] - 50)
    streak = config["streak"]
    score += min(streak["top10_bonus_cap"], item["top10_streak"] * streak["top10_bonus_per_day"])
    score -= max(0, item["top10_streak"] - streak["fatigue_starts_after_days"]) * streak["fatigue_per_extra_day"]
    returning = config["return_bonus"]
    return score + min(item["days_outside_top10"], returning["max_days"]) * returning["per_day_outside_top10"]


def movement_for(previous: dict[str, Any], rank: int, labels: dict[str, str]) -> str:
    if not previous["ever_charted"]:
        return labels["first_ever_top10"]
    if previous["last_rank"] is None:
        return labels["reentry_after_absence"]
    if previous["last_rank"] == rank:
        return labels["same_rank"]
    delta = previous["last_rank"] - rank
    return f"{labels['up'] if delta > 0 else labels['down']}{abs(delta)}"


def generate_chart(chart_day: date, tracks: list[dict[str, Any]], state: dict[str, Any], config: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    normalise_state(state, tracks, config)
    update_daily_random_state(state, tracks, config, rng)
    ranked = sorted(((daily_score(track, state, config), track) for track in tracks if track["enabled"]), key=lambda row: (-row[0], row[1]["track_id"]))
    selected, artists = [], set()
    for _, track in ranked:
        if track["artist"] in artists:
            continue
        selected.append(track); artists.add(track["artist"])
        if len(selected) == config["top_n"]:
            break
    if len(selected) != config["top_n"]:
        raise RuntimeError("fewer than 10 distinct enabled artists")
    prior = {str(track["track_id"]): copy.deepcopy(state["tracks"][str(track["track_id"])]) for track in tracks}
    chart = []
    for rank, track in enumerate(selected, start=1):
        previous = prior[str(track["track_id"])]
        chart.append({"rank": rank, "track_id": track["track_id"], "artist": track["artist"], "title": track["title"],
                      "movement": movement_for(previous, rank, config["movement_labels"]),
                      "days_at_number_1": previous["number1_streak"] + 1 if rank == 1 else 0,
                      "top10_streak": previous["top10_streak"] + 1})
    ranks = {row["track_id"]: row["rank"] for row in chart}
    for track in tracks:
        item, rank = state["tracks"][str(track["track_id"])], ranks.get(track["track_id"])
        if rank is None:
            item["last_rank"] = None; item["top10_streak"] = 0; item["number1_streak"] = 0; item["days_outside_top10"] += 1
        else:
            item["last_rank"] = rank; item["top10_streak"] += 1; item["number1_streak"] = item["number1_streak"] + 1 if rank == 1 else 0; item["days_outside_top10"] = 0; item["ever_charted"] = True
    state["last_generated_chart_date"] = chart_day.isoformat()
    return {"date": chart_day.isoformat(), "chart": chart}


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def load_state(path: Path, tracks: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return initial_state(tracks, config)
    return normalise_state(json.loads(path.read_text(encoding="utf-8")), tracks, config)


def chart_date_for_jst(moment: datetime, config: dict[str, Any]) -> date:
    jst = moment.astimezone(ZoneInfo(config["timezone"]))
    return jst.date() if jst.hour >= config["chart_boundary_hour"] else jst.date() - timedelta(days=1)


def simulation_start_date(seed: int, explicit: str | None) -> date:
    if explicit:
        return date.fromisoformat(explicit)
    digits = str(seed)
    if len(digits) == 8:
        try:
            return datetime.strptime(digits, "%Y%m%d").date()
        except ValueError:
            pass
    return date(2000, 1, 1)


def simulate(days: int, seed: int, tracks: list[dict[str, Any]], config: dict[str, Any], start_day: date) -> list[dict[str, Any]]:
    state, rng = initial_state(tracks, config), random.Random(seed)
    return [generate_chart(start_day + timedelta(days=index), tracks, state, config, rng) for index in range(days)]


def today(chart_day: date, tracks: list[dict[str, Any]], config: dict[str, Any], state_path: Path, output_dir: Path, generated_at: datetime | None = None) -> dict[str, Any]:
    state = load_state(state_path, tracks, config)
    daily_path = output_dir / f"{chart_day.isoformat()}.json"
    last_generated = state["last_generated_chart_date"]
    if last_generated == chart_day.isoformat():
        if not daily_path.exists():
            raise RuntimeError("state says chart already exists but daily output is missing")
        return json.loads(daily_path.read_text(encoding="utf-8"))

    last_day = date.fromisoformat(last_generated) if last_generated else None
    if last_day and last_day > chart_day:
        if not daily_path.exists():
            raise RuntimeError("state is newer than the requested chart date and its daily output is missing")
        return json.loads(daily_path.read_text(encoding="utf-8"))

    timestamp = (generated_at or datetime.now(ZoneInfo(config["timezone"]))).astimezone(ZoneInfo(config["timezone"])).isoformat()
    first_day = chart_day if last_day is None else last_day + timedelta(days=1)
    payload: dict[str, Any] | None = None
    for day_offset in range((chart_day - first_day).days + 1):
        day = first_day + timedelta(days=day_offset)
        result = generate_chart(day, tracks, state, config, random.Random(int(day.strftime("%Y%m%d"))))
        payload = {"date": result["date"], "generated_at": timestamp, "chart": result["chart"]}
        atomic_write_json(output_dir / f"{day.isoformat()}.json", payload)

    if payload is None:
        raise RuntimeError("no chart was generated")
    atomic_write_json(output_dir / "latest.json", payload)
    atomic_write_json(state_path, state)
    return payload


def project(days: int, tracks: list[dict[str, Any]], config: dict[str, Any], state_path: Path, output_dir: Path) -> None:
    """Write deterministic future chart files without advancing production state."""
    if days < 1:
        raise ValueError("projection days must be positive")
    state = copy.deepcopy(load_state(state_path, tracks, config))
    last_generated = state["last_generated_chart_date"]
    if not last_generated:
        raise RuntimeError("cannot project before the first production chart exists")
    first_day = date.fromisoformat(last_generated) + timedelta(days=1)
    timezone = ZoneInfo(config["timezone"])
    for day_offset in range(days):
        chart_day = first_day + timedelta(days=day_offset)
        result = generate_chart(chart_day, tracks, state, config, random.Random(int(chart_day.strftime("%Y%m%d"))))
        projected_at = datetime(chart_day.year, chart_day.month, chart_day.day, config["chart_boundary_hour"], tzinfo=timezone).isoformat()
        payload = {"date": result["date"], "generated_at": projected_at, "chart": result["chart"]}
        atomic_write_json(output_dir / f"{chart_day.isoformat()}.json", payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HACHIJO HOT 10 F4.1-B")
    commands = parser.add_subparsers(dest="command", required=True)
    today_parser = commands.add_parser("today"); today_parser.add_argument("--date"); today_parser.add_argument("--state-file", default=str(STATE_PATH)); today_parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    project_parser = commands.add_parser("project"); project_parser.add_argument("--days", type=int, required=True); project_parser.add_argument("--state-file", default=str(STATE_PATH)); project_parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    sim_parser = commands.add_parser("simulate"); sim_parser.add_argument("--days", type=int, required=True); sim_parser.add_argument("--seed", type=int, required=True); sim_parser.add_argument("--start-date")
    reset_parser = commands.add_parser("reset-state"); reset_parser.add_argument("--state-file", default=str(STATE_PATH)); reset_parser.add_argument("--output-dir", default=str(OUTPUT_DIR)); reset_parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv); config = load_config()
    tracks = load_tracks(resolve_master_path(config))
    if args.command == "simulate":
        if args.days < 1: raise ValueError("--days must be positive")
        print(json.dumps(simulate(args.days, args.seed, tracks, config, simulation_start_date(args.seed, args.start_date)), ensure_ascii=False, indent=2)); return 0
    if args.command == "reset-state":
        if not args.yes: raise ValueError("reset-state requires --yes")
        Path(args.state_file).unlink(missing_ok=True); return 0
    if args.command == "project":
        project(args.days, tracks, config, Path(args.state_file), Path(args.output_dir)); return 0
    day = date.fromisoformat(args.date) if args.date else chart_date_for_jst(datetime.now(ZoneInfo(config["timezone"])), config)
    print(json.dumps(today(day, tracks, config, Path(args.state_file), Path(args.output_dir)), ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
