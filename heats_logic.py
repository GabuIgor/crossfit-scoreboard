from __future__ import annotations

from typing import Any, Dict, List


def serialize_heats_for_public(db: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Возвращает заходы в безопасном для public JSON формате.

    Поддерживает несколько возможных структур в db:
    - db["heats"] как словарь {score_id: [...]}
    - db["heats"] как список
    - отсутствие db["heats"]
    """

    heats = db.get("heats", {})

    if isinstance(heats, dict):
        result: Dict[str, List[Dict[str, Any]]] = {}

        for workout_id, items in heats.items():
            if not isinstance(items, list):
                result[str(workout_id)] = []
                continue

            normalized: List[Dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue

                normalized.append(
                    {
                        "heat": item.get("heat"),
                        "lane": item.get("lane"),
                        "athlete_id": item.get("athlete_id"),
                        "division_id": item.get("division_id"),
                        "full_name": item.get("full_name"),
                        "club": item.get("club"),
                        "city": item.get("city"),
                        "flag": item.get("flag"),
                    }
                )

            result[str(workout_id)] = normalized

        return result

    if isinstance(heats, list):
        normalized_list: List[Dict[str, Any]] = []
        for item in heats:
            if not isinstance(item, dict):
                continue

            normalized_list.append(
                {
                    "heat": item.get("heat"),
                    "lane": item.get("lane"),
                    "athlete_id": item.get("athlete_id"),
                    "division_id": item.get("division_id"),
                    "full_name": item.get("full_name"),
                    "club": item.get("club"),
                    "city": item.get("city"),
                    "flag": item.get("flag"),
                    "score_id": item.get("score_id"),
                }
            )

        return {"items": normalized_list}

    return {}