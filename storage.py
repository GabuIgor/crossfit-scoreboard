import json
import os
from pathlib import Path
from typing import Dict, Any

from config import DATA_DIR, DB_FILE, DATA_FLAGS_DIR, DIVISIONS, DEFAULT_SCORES


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FLAGS_DIR.mkdir(parents=True, exist_ok=True)


def default_db() -> Dict[str, Any]:
    """
    Единственный источник правды — data/db.json.
    Структура:
      db = {
        "settings": {...},
        "participants": [ ... ],
        "results": { "<athlete_id>": { "<score_id>": {...} } },
        "heats": { ... }
      }
    """
    return {
        "settings": {
            "division_limits": {
                "BEGSCAL_M": 16,
                "BEGSCAL_F": 8,
                "INT_M": 16,
                "INT_F": 8,
            },
            "scores": DEFAULT_SCORES,
        },
        "participants": [],
        "results": {},
        "heats": {},
        "meta": {
            "version": 2,
        },
    }


def _normalize_db(db: Dict[str, Any]) -> Dict[str, Any]:
    base = default_db()
    if not isinstance(db, dict):
        return base

    settings = db.get("settings") if isinstance(db.get("settings"), dict) else {}
    division_limits = settings.get("division_limits") if isinstance(settings.get("division_limits"), dict) else {}
    scores = settings.get("scores") if isinstance(settings.get("scores"), list) and settings.get("scores") else DEFAULT_SCORES

    normalized = {
        "settings": {
            "division_limits": {**base["settings"]["division_limits"], **division_limits},
            "scores": scores,
        },
        "participants": db.get("participants") if isinstance(db.get("participants"), list) else [],
        "results": db.get("results") if isinstance(db.get("results"), dict) else {},
        "heats": db.get("heats") if isinstance(db.get("heats"), dict) else {},
        "meta": db.get("meta") if isinstance(db.get("meta"), dict) else {},
    }

    normalized["meta"].setdefault("version", 2)
    return normalized


def load_db() -> Dict[str, Any]:
    ensure_dirs()
    if DB_FILE.exists():
        with DB_FILE.open("r", encoding="utf-8") as f:
            db = json.load(f)
        normalized = _normalize_db(db)
        if normalized != db:
            save_db(normalized)
        return normalized

    db = default_db()
    save_db(db)
    return db


def save_db(db: Dict[str, Any]) -> None:
    ensure_dirs()
    normalized = _normalize_db(db)
    tmp_file = DB_FILE.with_suffix(DB_FILE.suffix + ".tmp")
    with tmp_file.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, DB_FILE)


def next_participant_id(db: Dict[str, Any]) -> int:
    participants = db.get("participants", [])
    if not participants:
        return 1
    return max(int(p.get("id", 0)) for p in participants) + 1


def get_division_title(division_id: str) -> str:
    for d in DIVISIONS:
        if d["id"] == division_id:
            return d["title"]
    return division_id


def count_participants_in_division(db: Dict[str, Any], division_id: str) -> int:
    return sum(1 for p in db.get("participants", []) if p.get("division_id") == division_id and not p.get("deleted", False))


def delete_participant(db: Dict[str, Any], participant_id: int) -> None:
    """
    Удаление делаем мягким: помечаем deleted=True.
    Это безопаснее: не потеряем историю.
    """
    for p in db.get("participants", []):
        if int(p["id"]) == int(participant_id):
            p["deleted"] = True
            break
