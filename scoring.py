from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from config import DIVISIONS
from storage import get_participants_in_division, get_score_def, get_results_for_score


def _score_type(score_def: Dict[str, Any]) -> str:
    return str(score_def.get("type", "reps")).lower()


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _extract_numeric_result(score_type: str, result: Optional[Dict[str, Any]]) -> Optional[float]:
    if not result:
        return None

    status = result.get("status")
    value = result.get("value")

    if status == "wd":
        return None

    if score_type == "time":
        if status == "capped":
            reps = _safe_float(value)
            return reps if reps is not None else None
        return _safe_float(value)

    return _safe_float(value)


def _sort_key_for_score(score_type: str, result: Optional[Dict[str, Any]]) -> Tuple:
    if not result:
        return (3, 0)

    status = result.get("status")
    value = result.get("value")

    if status == "wd":
        return (4, 0)

    if score_type == "time":
        if status == "capped":
            reps = _safe_float(value)
            if reps is None:
                return (2, 0)
            return (1, -reps)
        time_value = _safe_float(value)
        if time_value is None:
            return (3, 0)
        return (0, time_value)

    numeric = _safe_float(value)
    if numeric is None:
        return (3, 0)
    return (0, -numeric)


def _points_for_place(place_index: int, participant_count: int) -> float:
    if participant_count <= 0:
        return 0.0
    if participant_count == 1:
        return 100.0
    step = 100.0 / participant_count
    points = 100.0 - place_index * step
    return round(max(points, 0.0), 2)


def _resolve_display_places(sorted_rows: List[Dict[str, Any]]) -> None:
    current_place = 0
    last_key = None

    for idx, row in enumerate(sorted_rows, start=1):
        result = row.get("result")
        if not result or result.get("status") == "wd":
            row["place"] = None
            row["display_place"] = None
            row["place_label"] = ""
            row["display_place_label"] = ""
            continue

        key = (
            result.get("status"),
            result.get("value"),
        )

        if key != last_key:
            current_place = idx
            last_key = key

        row["place"] = current_place
        row["display_place"] = current_place
        row["place_label"] = str(current_place)
        row["display_place_label"] = str(current_place)


def build_ranking(db: Dict[str, Any], division_id: str, score_id: str) -> List[Dict[str, Any]]:
    participants = [
        p for p in get_participants_in_division(db, division_id)
        if not p.get("deleted", False)
    ]
    score_def = get_score_def(db, score_id)
    score_type = _score_type(score_def)
    raw_results = get_results_for_score(db, division_id, score_id)

    result_by_athlete = {
        int(r["athlete_id"]): r
        for r in raw_results
        if r.get("athlete_id") is not None
    }

    rows: List[Dict[str, Any]] = []
    for p in participants:
        athlete_id = int(p["id"])
        result = result_by_athlete.get(athlete_id)
        rows.append({
            "athlete_id": athlete_id,
            "full_name": p.get("full_name", ""),
            "participant": p,
            "result": result,
            "points": 0.0,
            "place": None,
            "display_place": None,
            "place_label": "",
            "display_place_label": "",
        })

    rows_sorted = sorted(
        rows,
        key=lambda r: (
            _sort_key_for_score(score_type, r.get("result")),
            r.get("full_name", "").lower(),
        )
    )

    _resolve_display_places(rows_sorted)

    valid_rows = [r for r in rows_sorted if r.get("place") is not None]
    participant_count = len(participants)

    for row in valid_rows:
        place_index = int(row["place"]) - 1
        row["points"] = _points_for_place(place_index, participant_count)

    for row in rows_sorted:
        if row.get("place") is None:
            row["points"] = 0.0

    return rows_sorted


def build_division_overall(db: Dict[str, Any], division_id: str) -> List[Dict[str, Any]]:
    participants = [
        p for p in get_participants_in_division(db, division_id)
        if not p.get("deleted", False)
    ]
    scores = db.get("settings", {}).get("scores", [])

    ranking_maps: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for score_def in scores:
        ranking = build_ranking(db, division_id, score_def["id"])
        ranking_maps[score_def["id"]] = {
            int(r["athlete_id"]): r for r in ranking
        }

    priority_score_id = db.get("settings", {}).get("team_scoring", {}).get("priority_score_id")

    rows: List[Dict[str, Any]] = []
    for p in participants:
        athlete_id = int(p["id"])
        total = 0.0
        priority_points = None

        for score_def in scores:
            score_id = score_def["id"]
            points = ranking_maps.get(score_id, {}).get(athlete_id, {}).get("points", 0.0) or 0.0
            total += float(points)
            if priority_score_id and score_id == priority_score_id:
                priority_points = float(points)

        rows.append({
            "athlete_id": athlete_id,
            "full_name": p.get("full_name", ""),
            "participant": p,
            "total": round(total, 2),
            "priority_points": priority_points,
            "place": None,
            "display_place": None,
            "place_label": "",
            "display_place_label": "",
        })

    rows.sort(
        key=lambda r: (
            -(r.get("total") or 0.0),
            -(r.get("priority_points") or -1e9),
            r.get("full_name", "").lower(),
        )
    )

    last_key = None
    current_place = 0
    for idx, row in enumerate(rows, start=1):
        key = (row.get("total"), row.get("priority_points"))
        if key != last_key:
            current_place = idx
            last_key = key
        row["place"] = current_place
        row["display_place"] = current_place
        row["place_label"] = str(current_place)
        row["display_place_label"] = str(current_place)

    return rows


def build_club_ranking(db: Dict[str, Any]) -> Dict[str, Any]:
    settings = db.get("settings", {})
    team_scoring = settings.get("team_scoring", {}) or {}
    enabled = bool(team_scoring.get("enabled", True))
    if not enabled:
        return {"rows": []}

    participants = [p for p in db.get("participants", []) if not p.get("deleted", False)]
    division_defs = {d["id"]: d for d in DIVISIONS}
    score_defs = settings.get("scores", [])

    overall_by_division = {
        d["id"]: build_division_overall(db, d["id"])
        for d in DIVISIONS
    }

    athlete_overall_map: Dict[int, Dict[str, Any]] = {}
    for div_id, rows in overall_by_division.items():
        for row in rows:
            athlete_overall_map[int(row["athlete_id"])] = row

    division_weights = team_scoring.get("division_weights", {}) or {}
    place_points = team_scoring.get("place_points", {"1": 3, "2": 2, "3": 1}) or {"1": 3, "2": 2, "3": 1}

    clubs: Dict[str, Dict[str, Any]] = {}

    for p in participants:
        club_name = (p.get("club") or "").strip()
        if not club_name:
            continue

        athlete_id = int(p["id"])
        overall = athlete_overall_map.get(athlete_id)
        if not overall:
            continue

        place = overall.get("place")
        if place not in (1, 2, 3):
            continue

        base_points = place_points.get(str(place), 0)
        division_id = p.get("division_id")
        weight = division_weights.get(division_id, 1)
        gained = float(base_points) * float(weight)

        club_row = clubs.setdefault(club_name, {
            "club": club_name,
            "total": 0.0,
            "athlete_count": 0,
            "first_places": 0,
            "breakdown": [],
        })

        club_row["total"] += gained
        club_row["athlete_count"] += 1
        if place == 1:
            club_row["first_places"] += 1

        club_row["breakdown"].append({
            "athlete_id": athlete_id,
            "full_name": p.get("full_name", ""),
            "division_id": division_id,
            "place": place,
            "points": gained,
        })

    rows = list(clubs.values())
    rows.sort(
        key=lambda r: (
            -(r.get("total") or 0.0),
            r.get("athlete_count") or 0,
            -(r.get("first_places") or 0),
            r.get("club", "").lower(),
        )
    )

    last_key = None
    current_place = 0
    for idx, row in enumerate(rows, start=1):
        key = (row.get("total"), row.get("athlete_count"), row.get("first_places"))
        if key != last_key:
            current_place = idx
            last_key = key
        row["place"] = current_place
        row["display_place"] = current_place
        row["place_label"] = str(current_place)
        row["display_place_label"] = str(current_place)
        row["total"] = round(float(row.get("total") or 0.0), 2)

    return {"rows": rows}