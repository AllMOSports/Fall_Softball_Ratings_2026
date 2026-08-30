#!/usr/bin/env python3
"""
build_fall_softball_schedule_2026.py

Converts fall_softball_games_2026_all.json (flat list of games, one row
per game with team1/team2/score1/score2) into
fall_softball_schedule_2026.json (per-team keyed format:
{"teams": {schoolName: [game, ...]}}), same shape the Sport Detail
snippet's SCHEDULE_URLS/HISTORICAL_SCHEDULE_URLS already expect for every
other sport/season -- this is a direct adaptation of
build_football_schedule_2026.py; the conversion logic itself isn't
sport-specific (it never reads anything about football), only the
docstring/filenames/field names changed.

Why this exists: fall_softball_games_2026_all.json comes from the same
kind of pipeline as football's (AllMOSports/Fall_Softball_Ratings_2026),
and its schema is flat (team1/team2/score1/score2) rather than pre-split
per team with predicted scores. This script bridges that gap so the
existing front-end code needs zero changes.

No ratings-based fields (predicted_team_score, predicted_opp_score,
off_delta, def_delta, ovr_delta) are computed here -- they're left null
on every game, same null-degradation pattern the front-end already
handles for girls_volleyball, since fall_softball_ratings_2026.json
presumably won't exist until some number of weeks into the season (same
reasoning as football's Week 3 cutoff -- confirm the actual timing for
softball, may not be identical). Once a ratings file exists, a second
pass can backfill those fields using the same
league_average + off_rating - def_rating formula used in prior seasons
-- this script does not need to change for that, only a new step added
after it.

home_away is also left null on every game: the source file carries no
home/away indicator, so this can't be determined from what's available.
The front-end already tolerates a null/missing home_away (falls back to
"at" instead of alternating "vs"/"at"); revisit if home/away ever gets
added to the source data.

FIELD NAME NOTE: football's version of this script carries through a
"forfeit"/"overtime" pair from the source file. Fall softball's scraper
(scrape_fall_softball_games_2026.py) produces "forfeit"/"extra_innings"
instead -- softball doesn't have overtime, it has extra innings -- so
this version reads/writes "extra_innings", not "overtime". If you ever
feed this script a games file that still uses the old "overtime" key,
it won't be picked up; rename it in the source or add a fallback below.

Usage:
    python build_fall_softball_schedule_2026.py <input_path_or_url> <output_path>

Example:
    python build_fall_softball_schedule_2026.py fall_softball_games_2026_all.json fall_softball_schedule_2026.json
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone


def load_games(source):
    """Load the flat game list from a local path or an http(s) URL."""
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source) as resp:
            return json.load(resp)
    with open(source, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_result(team_score, opp_score):
    """Mirror the W/L/T logic every other season's schedule file uses.
    Returns None (upcoming/unplayed game) if either score is missing."""
    if team_score is None or opp_score is None:
        return None
    if team_score > opp_score:
        return "W"
    if team_score < opp_score:
        return "L"
    return "T"


def make_game_entry(date, opponent, team_score, opp_score, forfeit, extra_innings):
    return {
        "date": date,
        "opponent": opponent,
        "home_away": None,  # not present in source; see module docstring
        "team_score": team_score,
        "opp_score": opp_score,
        "result": compute_result(team_score, opp_score),
        # Ratings-dependent fields -- intentionally null until a fall
        # softball ratings feed exists (see module docstring).
        "predicted_team_score": None,
        "predicted_opp_score": None,
        "off_delta": None,
        "def_delta": None,
        "ovr_delta": None,
        # Carried through from the source file for future use (not yet
        # read by the front-end, but cheap to keep rather than discard).
        "forfeit": bool(forfeit),
        "extra_innings": bool(extra_innings),
    }


def build_schedule(games, season=2026):
    teams = {}

    for g in games:
        date = g.get("date")
        team1 = g.get("team1")
        team2 = g.get("team2")
        score1 = g.get("score1")
        score2 = g.get("score2")
        forfeit = g.get("forfeit", False)
        extra_innings = g.get("extra_innings", False)

        if not team1 or not team2:
            # Malformed row -- skip rather than crash the whole build.
            print(f"Skipping malformed game (missing team name): {g}", file=sys.stderr)
            continue

        teams.setdefault(team1, []).append(
            make_game_entry(date, team2, score1, score2, forfeit, extra_innings)
        )
        teams.setdefault(team2, []).append(
            make_game_entry(date, team1, score2, score1, forfeit, extra_innings)
        )

    # Keep each team's games in chronological order (ISO date strings
    # sort correctly as plain strings; None dates sort last).
    for schedule in teams.values():
        schedule.sort(key=lambda entry: entry["date"] or "9999-99-99")

    return {
        "season": season,
        "generated": datetime.now(timezone.utc).isoformat(),
        "teams": teams,
    }


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    input_source, output_path = sys.argv[1], sys.argv[2]

    games = load_games(input_source)
    schedule = build_schedule(games)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2)

    team_count = len(schedule["teams"])
    game_count = len(games)
    print(f"Built {output_path}: {team_count} teams, {game_count} source games.")


if __name__ == "__main__":
    main()
