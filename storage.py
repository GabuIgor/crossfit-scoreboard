import json
import os
from typing import Dict, Any

from config import DATA_DIR, DB_FILE, DATA_FLAGS_DIR, DIVISIONS, DEFAULT_SCORES


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FLAGS_DIR.mkdir(parents=True, exist_ok=True)


def default_db() -> Dict[str, Any]:
    return {
        "settings": {
            "division_limits": {
                "BEGSCAL_M": 16,
                "BEGSCAL_F": 8,
                "INT_M": 16,
                "INT_F": 8,
            },
            "scores": DEFAULT_SCORES,
            "display": {
                "main": {
                    "page_title_font_size": 22,
                    "section_title_font_size": 18,
                    "card_title_font_size": 16,
                    "table_font_size": 11,
                    "athlete_font_size": 13,
                    "meta_font_size": 11,
                    "heat_title_font_size": 16,
                    "heat_text_font_size": 12,
                },
                "mobile": {
                    "table_font_size": 12,
                    "secondary_font_size": 11,
                    "heat_title_font_size": 16,
                    "heat_text_font_size": 14,
                    "heat_lane_font_size": 13,
                    "heat_card_width": 180,
                },
            },
        },
        "participants": [],
        "results": {},
        "heats": {},
        "meta": {
            "version": 3,
        },
    }


def _normalize_participant(raw: Any) -> Dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    try:
        participant_id = int(raw.get("id"))
    except (TypeError, ValueError):
        return None

    sex = str(raw.get("sex") or "").strip().upper()
    if sex not in {"M", "F"}:
        sex = "M"

    category = str(raw.get("category") or "").strip().upper()
    if category not in {"BEGSCAL", "INT"}:
        category = "BEGSCAL"

    division_id = str(raw.get("division_id") or "").strip()
    if division_id not in {d["id"] for d in DIVISIONS}:
        if category == "BEGSCAL" and sex == "M":
            division_id = "BEGSCAL_M"
        elif category == "BEGSCAL" and sex == "F":
            division_id = "BEGSCAL_F"
        elif category == "INT" and sex == "M":
            division_id = "INT_M"
        else:
            division_id = "INT_F"

    try:
        age = int(raw.get("age", 0) or 0)
    except (TypeError, ValueError):
        age = 0

    return {
        "id": participant_id,
        "full_name": str(raw.get("full_name") or "").strip(),
        "sex": sex,
        "age": age,
        "category": category,
        "division_id": division_id,
        "region": str(raw.get("region") or "").strip(),
        "city": str(raw.get("city") or "").strip(),
        "club": str(raw.get("club") or "").strip(),
        "flag_path": raw.get("flag_path") or None,
        "deleted": bool(raw.get("deleted", False)),
    }


def _normalize_db(db: Dict[str, Any]) -> Dict[str, Any]:
    base = default_db()
    if not isinstance(db, dict):
        return base

    settings = db.get("settings") if isinstance(db.get("settings"), dict) else {}
    division_limits = settings.get("division_limits") if isinstance(settings.get("division_limits"), dict) else {}
    scores = settings.get("scores") if isinstance(settings.get("scores"), list) and settings.get("scores") else DEFAULT_SCORES

    participants_raw = db.get("participants") if isinstance(db.get("participants"), list) else []
    participants = []
    for item in participants_raw:
        normalized = _normalize_participant(item)
        if normalized is not None:
            participants.append(normalized)

    display_settings = settings.get("display") if isinstance(settings.get("display"), dict) else {}
    base_display = base["settings"].get("display", {})
    main_display = display_settings.get("main") if isinstance(display_settings.get("main"), dict) else {}
    mobile_display = display_settings.get("mobile") if isinstance(display_settings.get("mobile"), dict) else {}

    normalized = {
        "settings": {
            "division_limits": {**base["settings"]["division_limits"], **division_limits},
            "scores": scores,
            "display": {
                "main": {**base_display.get("main", {}), **main_display},
                "mobile": {**base_display.get("mobile", {}), **mobile_display},
            },
        },
        "participants": participants,
        "results": db.get("results") if isinstance(db.get("results"), dict) else {},
        "heats": db.get("heats") if isinstance(db.get("heats"), dict) else {},
        "meta": db.get("meta") if isinstance(db.get("meta"), dict) else {},
    }

    normalized["meta"].setdefault("version", 3)
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
    for p in db.get("participants", []):
        if int(p["id"]) == int(participant_id):
            p["deleted"] = True
            break
