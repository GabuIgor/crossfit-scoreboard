from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional




def _flag_data_uri(flag_path: Optional[str]) -> Optional[str]:
    if not flag_path:
        return None

    src = Path(flag_path)
    if not src.is_absolute():
        src = Path.cwd() / src
    if not src.exists() or not src.is_file():
        return None

    mime_type, _ = mimetypes.guess_type(src.name)
    mime_type = mime_type or "image/png"

    try:
        encoded = base64.b64encode(src.read_bytes()).decode("ascii")
    except OSError:
        return None

    return f"data:{mime_type};base64,{encoded}"

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
                                    "region": participant.get("region", "") or participant.get("city", ""),
                                    "city": participant.get("city", ""),
                                    "flag": _flag_data_uri(participant.get("flag_path")),
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
