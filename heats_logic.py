from __future__ import annotations

from typing import Any, Dict, List


def _participant_map(db: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for p in db.get("participants", []):
        if p.get("deleted", False):
            continue
        try:
            result[int(p.get("id"))] = p
        except (TypeError, ValueError):
            continue
    return result


def _score_title_map(db: Dict[str, Any]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for s in db.get("settings", {}).get("scores", []):
        sid = str(s.get("id", "")).strip()
        if sid:
            result[sid] = s.get("title") or sid
    result.setdefault("WOD2", "Комплекс 2")
    return result


def serialize_heats_for_public(db: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Нормализует heats в public-формат, который ожидают docs/index.html и docs/mobile.html:

    {
      "WOD1": {
        "title": "Комплекс 1",
        "divisions": {
          "INT_M": [
            {
              "heat": 1,
              "assignments": [
                {"lane": 1, "athlete_id": 10, "full_name": "...", ...}
              ]
            }
          ]
        }
      }
    }
    """

    heats = db.get("heats", {})
    if not isinstance(heats, dict):
        return {}

    participants = _participant_map(db)
    score_titles = _score_title_map(db)
    public: Dict[str, Dict[str, Any]] = {}

    for workout_id, workout_data in heats.items():
        wid = str(workout_id)
        workout_public: Dict[str, Any] = {
            "title": score_titles.get(wid, wid),
            "divisions": {},
        }

        if not isinstance(workout_data, dict):
            public[wid] = workout_public
            continue

        for division_id, division_heats in workout_data.items():
            div_id = str(division_id)
            normalized_heats: List[Dict[str, Any]] = []

            if isinstance(division_heats, list):
                for heat in division_heats:
                    if not isinstance(heat, dict):
                        continue

                    assignments_public: List[Dict[str, Any]] = []
                    assignments = heat.get("assignments", [])
                    if isinstance(assignments, list):
                        for assignment in assignments:
                            if not isinstance(assignment, dict):
                                continue

                            athlete_id = assignment.get("athlete_id")
                            try:
                                athlete_key = int(athlete_id)
                            except (TypeError, ValueError):
                                athlete_key = None

                            participant = participants.get(athlete_key) if athlete_key is not None else {}
                            assignments_public.append(
                                {
                                    "lane": assignment.get("lane"),
                                    "athlete_id": athlete_key,
                                    "full_name": participant.get("full_name", ""),
                                    "club": participant.get("club", ""),
                                    "city": participant.get("city", ""),
                                    "flag": f"flags/athlete_{athlete_key}.png" if participant.get("flag_path") and athlete_key is not None else None,
                                }
                            )

                    normalized_heats.append(
                        {
                            "heat": heat.get("heat"),
                            "assignments": assignments_public,
                        }
                    )

            workout_public["divisions"][div_id] = normalized_heats

        public[wid] = workout_public

    return public
