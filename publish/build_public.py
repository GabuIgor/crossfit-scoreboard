import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import DOCS_DIR, DOCS_RESULTS_FILE, DOCS_FLAGS_DIR, DIVISIONS
from heats_logic import serialize_heats_for_public
from storage import load_db
from scoring import build_ranking, total_points_for_athlete
from utils import display_result_value


def ensure_docs_dirs() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_FLAGS_DIR.mkdir(parents=True, exist_ok=True)


def _public_result_text(score_def: Dict[str, Any], result: Optional[Dict[str, Any]]) -> str:
    if not result:
        return ""

    status = result.get("status")
    value = result.get("value")

    if status == "wd":
        return "WD"

    if status == "capped":
        pretty = display_result_value(score_def, value)
        return f"CAP {pretty}" if pretty else "CAP"

    return display_result_value(score_def, value)


def _assign_places_by_total(rows: List[Dict[str, Any]]) -> None:
    place = 0
    prev_total = None

    for index, row in enumerate(rows, start=1):
        total = float(row.get("total") or 0.0)
        if prev_total is None or total != prev_total:
            place = index
        row["place"] = place
        prev_total = total


def _collect_existing_flags(db: Dict[str, Any]) -> Dict[int, Path]:
    result: Dict[int, Path] = {}

    for p in db.get("participants", []):
        if p.get("deleted", False):
            continue

        raw_flag_path = p.get("flag_path")
        if not raw_flag_path:
            continue

        src = Path(raw_flag_path)
        if not src.exists() or not src.is_file():
            continue

        try:
            athlete_id = int(p["id"])
        except Exception:
            continue

        result[athlete_id] = src

    return result


def copy_flags_to_docs(flag_sources: Dict[int, Path]) -> None:
    ensure_docs_dirs()

    if DOCS_FLAGS_DIR.exists():
        for f in DOCS_FLAGS_DIR.glob("*"):
            if f.is_file():
                f.unlink()

    for athlete_id, src in flag_sources.items():
        dst = DOCS_FLAGS_DIR / f"athlete_{athlete_id}.png"
        shutil.copyfile(src, dst)


def build_public_payload(db: Dict[str, Any], flag_sources: Dict[int, Path]) -> Dict[str, Any]:
    settings = db["settings"]
    scores = settings["scores"]

    payload: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "divisions": {},
        "scores": scores,
        "heats": serialize_heats_for_public(db),
    }

    for d in DIVISIONS:
        div_id = d["id"]
        participants = [
            p for p in db.get("participants", [])
            if p.get("division_id") == div_id and not p.get("deleted", False)
        ]

        points_maps = {}
        result_maps = {}

        for s in scores:
            ranking = build_ranking(db, div_id, s["id"])
            points_maps[s["id"]] = {r["athlete_id"]: r.get("points") for r in ranking}
            result_maps[s["id"]] = {r["athlete_id"]: r.get("result") for r in ranking}

        rows = []
        sorted_participants = sorted(
            participants,
            key=lambda p: (-total_points_for_athlete(db, int(p["id"])), p.get("full_name", ""))
        )

        for p in sorted_participants:
            aid = int(p["id"])
            flag_rel = f"flags/athlete_{aid}.png" if aid in flag_sources else None

            row = {
                "place": None,
                "id": aid,
                "full_name": p.get("full_name", ""),
                "age": p.get("age", ""),
                "club": p.get("club", ""),
                "city": p.get("city", ""),
                "category": p.get("category", ""),
                "division_id": div_id,
                "flag": flag_rel,
                "scores": {},
                "total": total_points_for_athlete(db, aid),
            }

            for s in scores:
                sid = s["id"]
                raw_result = result_maps[sid].get(aid)
                row["scores"][sid] = {
                    "points": points_maps[sid].get(aid),
                    "result": raw_result,
                    "result_text": _public_result_text(s, raw_result),
                }

            rows.append(row)

        _assign_places_by_total(rows)

        payload["divisions"][div_id] = {
            "title": d["title"],
            "rows": rows,
        }

    return payload


def write_public_results(payload: Dict[str, Any]) -> None:
    ensure_docs_dirs()
    with DOCS_RESULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_all() -> None:
    db = load_db()
    flag_sources = _collect_existing_flags(db)
    copy_flags_to_docs(flag_sources)
    payload = build_public_payload(db, flag_sources)
    write_public_results(payload)


if __name__ == "__main__":
    build_all()
    print(f"OK: wrote {DOCS_RESULTS_FILE}")