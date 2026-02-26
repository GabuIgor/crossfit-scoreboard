import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from config import PUBLIC_DIR, PUBLIC_RESULTS_FILE, PUBLIC_FLAGS_DIR, DIVISIONS
from storage import load_db
from scoring import build_ranking, total_points_for_athlete


def ensure_public_dirs() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_FLAGS_DIR.mkdir(parents=True, exist_ok=True)


def build_public_payload() -> Dict[str, Any]:
    db = load_db()
    settings = db["settings"]
    scores = settings["scores"]

    payload: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "divisions": {},
        "scores": scores,
        "heats": db.get("heats", {}),
    }

    # Упаковываем таблицы по дивизионам
    for d in DIVISIONS:
        div_id = d["id"]
        participants = [
            p for p in db.get("participants", [])
            if p.get("division_id") == div_id and not p.get("deleted", False)
        ]

        # points map per score
        points_maps = {}
        result_maps = {}
        for s in scores:
            ranking = build_ranking(db, div_id, s["id"])
            points_maps[s["id"]] = {r["athlete_id"]: r.get("points") for r in ranking}
            result_maps[s["id"]] = {r["athlete_id"]: r.get("result") for r in ranking}

        rows = []
        for p in participants:
            aid = int(p["id"])
            row = {
                "id": aid,
                "full_name": p.get("full_name", ""),
                "age": p.get("age", ""),
                "club": p.get("club", ""),
                "city": p.get("city", ""),
                "category": p.get("category", ""),
                "division_id": div_id,
                "flag": None,  # будет относительный путь для public
                "scores": {},
                "total": total_points_for_athlete(db, aid),
            }

            # флаг: если есть локальный, мы при сборке скопируем в public/flags
            fp = p.get("flag_path")
            if fp:
                # ожидаем имя вида data/flags/athlete_<id>.png
                # в public будет flags/athlete_<id>.png
                row["flag"] = f"flags/athlete_{aid}.png"

            for s in scores:
                sid = s["id"]
                pts = points_maps[sid].get(aid)
                res = result_maps[sid].get(aid)
                # для public отдадим и pts, и raw result
                row["scores"][sid] = {
                    "points": pts,   # None => "-"
                    "result": res,   # None => "-"
                }

            rows.append(row)

        # сортируем по total desc
        rows.sort(key=lambda r: (-float(r["total"]), r["full_name"]))

        payload["divisions"][div_id] = {
            "title": d["title"],
            "rows": rows
        }

    return payload


def copy_flags_to_public(payload: Dict[str, Any]) -> None:
    """
    Копируем флаги, которые используются, из data/flags в public/flags.
    """
    ensure_public_dirs()

    # очищаем public/flags (безопасно)
    if PUBLIC_FLAGS_DIR.exists():
        for f in PUBLIC_FLAGS_DIR.glob("*"):
            if f.is_file():
                f.unlink()

    # копируем необходимые
    # ищем по rows flag="flags/athlete_<id>.png"
    db = load_db()
    for p in db.get("participants", []):
        if p.get("deleted", False):
            continue
        fp = p.get("flag_path")
        if not fp:
            continue
        src = Path(fp)
        if not src.exists():
            continue
        dst = PUBLIC_FLAGS_DIR / f"athlete_{p['id']}.png"
        try:
            shutil.copyfile(src, dst)
        except Exception:
            pass


def write_public_results(payload: Dict[str, Any]) -> None:
    ensure_public_dirs()
    with PUBLIC_RESULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_all() -> None:
    payload = build_public_payload()
    copy_flags_to_public(payload)
    write_public_results(payload)


if __name__ == "__main__":
    build_all()
    print(f"OK: wrote {PUBLIC_RESULTS_FILE}")