import json
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
        "heats": { ... }   # пока каркас
      }
    """
    return {
        "settings": {
            # лимиты участников по дивизионам (можно менять в Settings)
            "division_limits": {
                "BEGSCAL_M": 16,
                "BEGSCAL_F": 8,
                "INT_M": 16,
                "INT_F": 8,
            },
            # описание зачётов/комплексов
            "scores": DEFAULT_SCORES,
        },
        "participants": [],
        "results": {},
        "heats": {},  # позже расширим
        "meta": {
            "version": 1
        }
    }


def load_db() -> Dict[str, Any]:
    ensure_dirs()
    if DB_FILE.exists():
        with DB_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)

    db = default_db()
    save_db(db)
    return db


def save_db(db: Dict[str, Any]) -> None:
    ensure_dirs()
    with DB_FILE.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


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