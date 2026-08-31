#!/usr/bin/env python3
"""Acceptance tests for the F4.1-B production engine."""

import copy
import hashlib
import inspect
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import hot10
import migrate_state_1601
import migrate_state_1726
import migrate_state_1728
import migrate_state_final_streak3


def summary(charts):
    daily = [{row["track_id"] for row in day["chart"]} for day in charts]
    replacements = [10 - len(left & right) for left, right in zip(daily, daily[1:])]
    rows = [row for day in charts for row in day["chart"]]
    return {
        "retention": sum(10 - value for value in replacements) / len(replacements),
        "replacements": sum(replacements) / len(replacements),
        "unique": len(set().union(*daily),),
        "new": sum(row["movement"] == "NEW" for row in rows), "re": sum(row["movement"] == "RE" for row in rows),
        "max1": max(row["days_at_number_1"] for row in rows), "maxtop": max(row["top10_streak"] for row in rows),
        "replacements_by_day": replacements,
    }


class Hot10ProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = hot10.load_config()
        cls.tracks = hot10.load_tracks(hot10.resolve_master_path(cls.config))
        cls.legacy_tracks = hot10.load_tracks(hot10.ROOT / "HACHIJO_HOT10_master_1389_F41_input.csv", 1389)

    def test_master_schema_and_ids(self):
        self.assertEqual(len(self.tracks), 1728)
        self.assertEqual({track["track_id"] for track in self.tracks}, set(range(1, 1729)))
        self.assertTrue(all(track["enabled"] in (0, 1) for track in self.tracks))
        self.assertTrue(all(0 <= track[field] <= 100 for track in self.tracks for field in hot10.SCORE_COLUMNS))

    def test_final_catalog_acceptance(self):
        path = hot10.resolve_master_path(self.config)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "fd2b040cb6fc15ebd1825bf233d95106ec18d2bcc07aaae6cd12d18ec48e7010")
        self.assertEqual(sum(track["enabled"] for track in self.tracks), 1718)
        self.assertEqual(next(track for track in self.tracks if track["track_id"] == 1594)["base_strength"], 76)
        deep10 = {452, 454, 458, 466, 470, 489, 496, 500, 502, 503}
        self.assertTrue(all(not track["enabled"] for track in self.tracks if track["track_id"] in deep10))
        exact = [(track["artist"], track["title"]) for track in self.tracks]
        normalised = [(artist.casefold().replace(" ", ""), title.casefold().replace(" ", "")) for artist, title in exact]
        self.assertEqual(len(exact), len(set(exact)))
        self.assertEqual(len(normalised), len(set(normalised)))

    def test_saturation_freshness_and_inertia(self):
        self.assertEqual(hot10.effective_hachijo_fit(70, self.config), 70)
        self.assertEqual(hot10.effective_hachijo_fit(100, self.config), 77.5)
        self.assertEqual(self.config["previous_day_inertia"], {"base_bonus_for_rank_1": 5.25, "rank_step_down": 0.35, "stickiness_scale": 0.015, "multiplier": 1.05})
        track = next(track for track in self.tracks if track["track_id"] == 2)
        self.assertGreaterEqual(hot10.effective_freshness(track, self.config), track["freshness_bonus"] * self.config["attenuated_freshness"]["minimum_factor"])
        self.assertLessEqual(hot10.effective_freshness(track, self.config), track["freshness_bonus"])

    def test_movement_labels(self):
        labels = self.config["movement_labels"]
        blank = hot10.blank_track_state()
        self.assertEqual(hot10.movement_for(blank, 1, labels), "NEW")
        reentry = blank | {"ever_charted": True}
        self.assertEqual(hot10.movement_for(reentry, 1, labels), "RE")
        prior = blank | {"ever_charted": True, "last_rank": 4}
        self.assertEqual(hot10.movement_for(prior, 4, labels), "→")
        self.assertEqual(hot10.movement_for(prior, 2, labels), "↑2")
        self.assertEqual(hot10.movement_for(prior, 7, labels), "↓3")

    def test_seeded_runtime_is_deterministic(self):
        charts = hot10.simulate(14, 20260826, self.legacy_tracks, self.config, datetime(2026, 8, 26).date())
        self.assertEqual(charts, hot10.simulate(14, 20260826, self.legacy_tracks, self.config, datetime(2026, 8, 26).date()))

    def test_streak_and_cooldown_boundaries(self):
        track = self.tracks[0]
        state = hot10.initial_state(self.tracks, self.config)
        item = state["tracks"]["1"]
        for streak in range(8):
            item["top10_streak"] = streak
            bonus = min(1.2, streak * 0.40)
            fatigue = max(0, streak - 3) * 0.45 + max(0, streak - 5) * 0.75
            self.assertAlmostEqual(hot10.daily_score(track, state, self.config) - hot10.static_score(track, self.config), bonus - fatigue)
        for streak in range(9):
            item["top10_streak"] = 0; item["number1_streak"] = streak
            self.assertAlmostEqual(hot10.daily_score(track, state, self.config) - hot10.static_score(track, self.config), -max(0, streak - 3) * 0.75)
        item.update({"ever_charted": True, "last_rank": None, "days_outside_top10": 179})
        self.assertFalse(hot10.is_track_eligible(track, state, self.config))
        item["days_outside_top10"] = 180
        self.assertTrue(hot10.is_track_eligible(track, state, self.config))
        item["ever_charted"] = False; item["days_outside_top10"] = 100; item["number1_streak"] = 0
        self.assertEqual(hot10.daily_score(track, state, self.config) - hot10.static_score(track, self.config), 1.125)
        chart_day = datetime(2026, 8, 26).date()
        state["artist_last_present_date"][track["artist"]] = "2026-07-09"
        self.assertFalse(hot10.is_artist_eligible(track, state, self.config, chart_day))
        state["artist_last_present_date"][track["artist"]] = "2026-07-08"
        self.assertTrue(hot10.is_artist_eligible(track, state, self.config, chart_day))
        state["artist_last_present_date"][track["artist"]] = "2026-08-25"
        self.assertTrue(hot10.is_artist_eligible(track, state, self.config, chart_day))

    def test_ten_tracks_and_one_artist_maximum(self):
        for day in hot10.simulate(30, 12345, self.tracks, self.config, datetime(2026, 8, 26).date()):
            self.assertEqual(len(day["chart"]), 10)
            self.assertEqual(len({row["artist"] for row in day["chart"]}), 10)

    def test_simulation_leaves_production_state_untouched(self):
        state = hot10.initial_state(self.tracks, self.config)
        original = copy.deepcopy(state)
        hot10.simulate(14, 20260826, self.tracks, self.config, datetime(2026, 8, 26).date())
        self.assertEqual(state, original)

    def test_1601_state_migration_preserves_existing_production_state(self):
        legacy_tracks = hot10.load_tracks(
            hot10.ROOT / "HACHIJO_HOT10_master_1589_F41_MICROTUNE.csv", 1589
        )
        before = hot10.initial_state(legacy_tracks, self.config)
        before["last_generated_chart_date"] = "2026-08-30"
        before["mood"]["emo"] = 1.25
        before["tracks"]["1"]["heat"] = 2.5
        snapshot = copy.deepcopy(before)
        after = migrate_state_1601.migrate_state(before)
        self.assertEqual(before, snapshot)
        self.assertEqual(after["version"], snapshot["version"])
        self.assertEqual(after["last_generated_chart_date"], snapshot["last_generated_chart_date"])
        self.assertEqual(after["mood"], snapshot["mood"])
        self.assertEqual(
            {key: after["tracks"][key] for key in map(str, range(1, 1590))},
            snapshot["tracks"],
        )
        self.assertEqual(set(after["tracks"]), {str(value) for value in range(1, 1602)})
        self.assertTrue(all(after["tracks"][str(value)] == hot10.blank_track_state() for value in range(1590, 1602)))

    def test_1726_state_migration_resets_only_identity_replacements(self):
        old_tracks = hot10.load_tracks(
            hot10.ROOT / "HACHIJO_HOT10_master_1601_F41_MONO4_HACHIJOBOOST1_FUKUSHIMA_MINUS1.csv", 1601
        )
        before = hot10.initial_state(old_tracks, self.config)
        before["last_generated_chart_date"] = "2026-08-31"
        before["mood"]["emo"] = 1.25
        before["tracks"]["1"]["heat"] = 2.5
        reset_ids = migrate_state_1726.replacement_ids()
        snapshot = copy.deepcopy(before)
        after = migrate_state_1726.migrate_state(before, self.tracks, self.config, reset_ids)
        migrate_state_1726.audit(before, after, self.tracks, self.config, reset_ids)
        self.assertEqual(before, snapshot)
        self.assertEqual(after["last_generated_chart_date"], snapshot["last_generated_chart_date"])
        self.assertEqual(after["mood"], snapshot["mood"])
        self.assertEqual(after["tracks"]["1"], snapshot["tracks"]["1"])
        self.assertTrue(all(after["tracks"][str(value)] == hot10.blank_track_state() for value in reset_ids))
        self.assertTrue(all(after["tracks"][str(value)] == hot10.blank_track_state() for value in range(1602, 1727)))

    def test_1728_state_migration_preserves_1726c_and_adds_only_two_tracks(self):
        old_tracks = hot10.load_tracks(
            hot10.ROOT / "HACHIJO_HOT10_master_1726_F41_EDGE125_90S00S_FULL.csv", 1726
        )
        before = hot10.initial_state(old_tracks, self.config)
        before["last_generated_chart_date"] = "2026-08-31"
        before["mood"]["emo"] = 1.25
        before["tracks"]["1"]["heat"] = 2.5
        snapshot = copy.deepcopy(before)
        after = migrate_state_1728.migrate_state(before, self.tracks, self.config)
        migrate_state_1728.audit(before, after, self.tracks, self.config)
        self.assertEqual(before, snapshot)
        self.assertEqual(after["last_generated_chart_date"], snapshot["last_generated_chart_date"])
        self.assertEqual(after["mood"], snapshot["mood"])
        self.assertEqual({key: after["tracks"][key] for key in map(str, range(1, 1727))}, snapshot["tracks"])
        self.assertTrue(all(after["tracks"][str(value)] == hot10.blank_track_state() for value in (1727, 1728)))

    def test_final_state_migration_preserves_dynamic_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = root / "output"; output.mkdir()
            before = hot10.initial_state(self.tracks, self.config)
            before["last_generated_chart_date"] = "2026-08-26"
            before["tracks"]["1"].update({"ever_charted": True, "heat": 2.5, "last_rank": 1})
            (output / "2026-08-26.json").write_text(json.dumps({"date": "2026-08-26", "chart": [{"track_id": 1, "artist": self.tracks[0]["artist"]}]}), encoding="utf-8")
            after = migrate_state_final_streak3.migrate_state(before, self.tracks, output)
            migrate_state_final_streak3.audit(before, after)
            self.assertEqual(after["tracks"]["1"]["last_top10_date"], "2026-08-26")
            self.assertEqual(after["artist_last_present_date"][self.tracks[0]["artist"]], "2026-08-26")

    def test_today_idempotence_and_atomic_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); state_path = root / "state.json"; output_dir = root / "output"
            generated_at = datetime(2026, 8, 26, 3, 5, tzinfo=ZoneInfo("Asia/Tokyo"))
            first = hot10.today(generated_at.date(), self.tracks, self.config, state_path, output_dir, generated_at)
            state_before = state_path.read_bytes()
            second = hot10.today(generated_at.date(), self.tracks, self.config, state_path, output_dir, generated_at)
            self.assertEqual(first, second)
            self.assertEqual(state_before, state_path.read_bytes())
            self.assertEqual(json.loads((output_dir / "latest.json").read_text(encoding="utf-8")), first)
            self.assertEqual(json.loads((output_dir / "2026-08-26.json").read_text(encoding="utf-8")), first)
            self.assertFalse(list(root.rglob("*.tmp")))

    def test_today_catches_up_each_missing_calendar_day(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); state_path = root / "state.json"; output_dir = root / "output"
            timezone = ZoneInfo("Asia/Tokyo")
            hot10.today(datetime(2026, 8, 26, 3, 5, tzinfo=timezone).date(), self.tracks, self.config, state_path, output_dir)
            caught_up = hot10.today(datetime(2026, 8, 28, 4, 5, tzinfo=timezone).date(), self.tracks, self.config, state_path, output_dir)
            self.assertEqual(caught_up["date"], "2026-08-28")
            self.assertTrue((output_dir / "2026-08-27.json").exists())
            self.assertTrue((output_dir / "2026-08-28.json").exists())
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["last_generated_chart_date"], "2026-08-28")

    def test_projection_writes_future_files_without_advancing_production_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); state_path = root / "state.json"; output_dir = root / "output"
            first = hot10.today(datetime(2026, 8, 26).date(), self.tracks, self.config, state_path, output_dir)
            state_before = state_path.read_bytes()
            latest_before = (output_dir / "latest.json").read_bytes()
            hot10.project(3, self.tracks, self.config, state_path, output_dir)
            self.assertEqual(state_path.read_bytes(), state_before)
            self.assertEqual((output_dir / "latest.json").read_bytes(), latest_before)
            self.assertEqual(json.loads((output_dir / "2026-08-29.json").read_text(encoding="utf-8"))["date"], "2026-08-29")
            self.assertEqual(first["date"], "2026-08-26")

    def test_chart_date_boundary(self):
        timezone = ZoneInfo("Asia/Tokyo")
        self.assertEqual(hot10.chart_date_for_jst(datetime(2026, 8, 26, 2, 59, tzinfo=timezone), self.config).isoformat(), "2026-08-25")
        self.assertEqual(hot10.chart_date_for_jst(datetime(2026, 8, 26, 3, 0, tzinfo=timezone), self.config).isoformat(), "2026-08-26")

    def test_runtime_score_has_no_metadata_branching(self):
        scoring_source = inspect.getsource(hot10.daily_score)
        for forbidden in ("release_year", "source", "category", "artist ==", "artist in"):
            self.assertNotIn(forbidden, scoring_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
