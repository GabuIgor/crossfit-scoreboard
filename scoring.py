from typing import Dict, Any, List, Tuple, Optional
import math


def _score_def(settings: Dict[str, Any], score_id: str) -> Dict[str, Any]:
    for s in settings.get("scores", []):
        if s["id"] == score_id:
            return s
    raise ValueError(f"Unknown score_id: {score_id}")


def _result_of(db: Dict[str, Any], athlete_id: int, score_id: str) -> Optional[Dict[str, Any]]:
    """
    result schema:
      {
        "status": "ok" | "capped" | "wd",
        "value": number,  # time_seconds OR reps OR weight OR capped_reps (если capped)
      }
    Если результата нет — None.
    """
    return db.get("results", {}).get(str(athlete_id), {}).get(score_id)


def _sort_key_for_score(score_type: str, result: Optional[Dict[str, Any]]) -> Tuple:
    """
    Общая идея сортировки:
    - ok всегда лучше capped для time
    - wd хуже всех (очки=0)
    - missing (None) вообще не ранжируем (будет внизу с "—")

    Возвращаем кортеж, чтобы Python мог сортировать:
    Меньше кортеж -> выше в рейтинге.
    """
    if result is None:
        # missing — в самый низ
        return (9,)

    status = result.get("status")
    value = result.get("value")

    if status == "wd":
        # снялся — хуже всех, но выше чем "missing"? можно в самый низ после всех
        return (8,)

    if score_type == "time":
        # ok time: лучше меньшие секунды
        if status == "ok":
            return (0, float(value))
        # capped: хуже любого ok time, но между capped сравниваем по reps (больше лучше)
        if status == "capped":
            return (1, -float(value))
        return (7,)

    # reps/weight: больше лучше
    if score_type in ("reps", "weight"):
        if status == "ok":
            return (0, -float(value))
        return (7,)

    return (7,)


def _points_for_place(place: int, n: int) -> float:
    """
    Очки пропорционально кол-ву участников:
      1 место = 100
      шаг = 100/n
      points = 100 - (place-1)*step

    place: 1..n
    n: число участников в дивизионе (активных)
    """
    if n <= 0:
        return 0.0
    step = 100.0 / float(n)
    pts = 100.0 - (place - 1) * step
    # не даём уйти ниже 0
    pts = max(0.0, pts)
    # округление (можно поменять)
    return round(pts, 2)


def build_ranking(db: Dict[str, Any], division_id: str, score_id: str) -> List[Dict[str, Any]]:
    """
    Возвращает строки рейтинга по одному зачёту внутри дивизиона.

    Правила:
    - missing -> показываем "—", очков нет (None)
    - wd -> очки 0
    - ничьи -> вариант B: одинаковый результат => одинаковое место => одинаковые очки этого места
    """
    settings = db["settings"]
    sdef = None
    for s in settings.get("scores", []):
        if s["id"] == score_id:
            sdef = s
            break
    if sdef is None:
        return []

    score_type = sdef["type"]

    participants = [
        p for p in db.get("participants", [])
        if p.get("division_id") == division_id and not p.get("deleted", False)
    ]

    # N для формулы очков — число участников в дивизионе.
    # Это соответствует "пропорционально количеству участников".
    n = len(participants)

    rows = []
    for p in participants:
        aid = int(p["id"])
        res = _result_of(db, aid, score_id)
        rows.append({
            "athlete_id": aid,
            "full_name": p.get("full_name", ""),
            "club": p.get("club", ""),
            "city": p.get("city", ""),
            "age": p.get("age", ""),
            "division_id": division_id,
            "result": res,  # raw
        })

    # сортировка для ранжируемых
    rows_sorted = sorted(rows, key=lambda r: _sort_key_for_score(score_type, r["result"]))

    # назначение мест с учетом ничьих (по "ключу сравнения результата")
    def cmp_value(r: Dict[str, Any]) -> Tuple:
        res = r["result"]
        if res is None:
            return ("missing",)
        status = res.get("status")
        val = res.get("value")
        # для time: ok сравниваем по времени, capped по reps, wd отдельно
        if score_type == "time":
            if status == "ok":
                return ("ok", float(val))
            if status == "capped":
                return ("capped", float(val))
            if status == "wd":
                return ("wd",)
        else:
            if status == "ok":
                return ("ok", float(val))
            if status == "wd":
                return ("wd",)
        return ("other",)

    place = 0
    index = 0
    prev_cmp = None

    for r in rows_sorted:
        index += 1
        cv = cmp_value(r)

        # missing — места не даем (будет внизу)
        if r["result"] is None:
            r["place"] = None
            r["points"] = None
            continue

        # wd — фиксируем place как "самый низ", но очки = 0
        if r["result"].get("status") == "wd":
            r["place"] = None
            r["points"] = 0.0
            continue

        # обычные результаты
        if prev_cmp is None:
            place = 1
        else:
            if cv != prev_cmp:
                place = index

        r["place"] = place
        r["points"] = _points_for_place(place, n)

        prev_cmp = cv

    return rows_sorted


def total_points_for_athlete(db: Dict[str, Any], athlete_id: int) -> float:
    settings = db["settings"]
    score_ids = [s["id"] for s in settings.get("scores", [])]

    # ищем дивизион атлета
    div_id = None
    for p in db.get("participants", []):
        if not p.get("deleted", False) and int(p["id"]) == int(athlete_id):
            div_id = p.get("division_id")
            break
    if div_id is None:
        return 0.0

    total = 0.0
    for sid in score_ids:
        ranking = build_ranking(db, div_id, sid)
        for r in ranking:
            if int(r["athlete_id"]) == int(athlete_id):
                pts = r.get("points")
                if pts is not None:
                    total += float(pts)
                break
    return round(total, 2)