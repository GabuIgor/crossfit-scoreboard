from __future__ import annotations

import copy
import random
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from config import DIVISIONS
from scoring import build_ranking
from storage import load_db, save_db
from utils import compact_page_style, participant_age

st.set_page_config(page_title="Heats", page_icon="🏁", layout="wide")
compact_page_style()

HEAT_WODS = ["WOD1", "WOD2", "WOD3"]
MAX_LANES = 4
AUTO_REQUEST_KEY = "pending_auto_build::heats"
AUTO_CONFIRM_KEY = "confirm_auto_build::heats"


def division_title_map() -> Dict[str, str]:
    return {d["id"]: d["title"] for d in DIVISIONS}


def ensure_heats(db: Dict[str, Any]) -> Dict[str, Any]:
    heats = db.setdefault("heats", {})
    if not isinstance(heats, dict):
        heats = {}
        db["heats"] = heats

    for wod in HEAT_WODS:
        if wod not in heats or not isinstance(heats[wod], dict):
            heats[wod] = {}

    return heats


def active_participants(db: Dict[str, Any], division_id: str) -> List[Dict[str, Any]]:
    items = [
        p for p in db.get("participants", [])
        if not p.get("deleted", False) and p.get("division_id") == division_id
    ]
    items.sort(key=lambda p: (p.get("full_name") or "").lower())
    return items


def participant_map(db: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for p in db.get("participants", []):
        if p.get("deleted", False):
            continue
        try:
            result[int(p.get("id"))] = p
        except (TypeError, ValueError):
            continue
    return result


def athlete_label(p: Optional[Dict[str, Any]]) -> str:
    if not p:
        return "— пусто —"
    name = p.get("full_name") or f"ID {p.get('id')}"
    club = str(p.get("club") or "").strip()
    city = str(p.get("city") or "").strip()
    if club and city:
        return f"{name} — {club}, {city}"
    if club:
        return f"{name} — {club}"
    if city:
        return f"{name} — {city}"
    return str(name)


def normalize_heat(heat: Any) -> Dict[str, Any]:
    if not isinstance(heat, dict):
        heat = {}

    try:
        heat_no = int(heat.get("heat", 1))
    except (TypeError, ValueError):
        heat_no = 1

    normalized_assignments: List[Dict[str, Any]] = []
    assignments = heat.get("assignments", [])
    if not isinstance(assignments, list):
        assignments = []

    for item in assignments:
        if not isinstance(item, dict):
            continue
        try:
            lane = int(item.get("lane"))
        except (TypeError, ValueError):
            continue

        athlete_id = item.get("athlete_id")
        if athlete_id in (None, ""):
            athlete_id = None
        else:
            try:
                athlete_id = int(athlete_id)
            except (TypeError, ValueError):
                athlete_id = None

        normalized_assignments.append({"lane": lane, "athlete_id": athlete_id})

    normalized_assignments.sort(key=lambda x: x["lane"])
    return {"heat": heat_no, "assignments": normalized_assignments}


def normalize_heats(heats_list: Any) -> List[Dict[str, Any]]:
    if not isinstance(heats_list, list):
        return []
    result = [normalize_heat(h) for h in heats_list]
    result.sort(key=lambda h: h.get("heat", 0))
    for idx, heat in enumerate(result, start=1):
        heat["heat"] = idx
    return result


def get_division_heats(db: Dict[str, Any], wod_id: str, division_id: str) -> List[Dict[str, Any]]:
    heats = ensure_heats(db)
    division_heats = heats[wod_id].get(division_id, [])
    division_heats = normalize_heats(division_heats)
    heats[wod_id][division_id] = division_heats
    return copy.deepcopy(division_heats)


def save_division_heats(db: Dict[str, Any], wod_id: str, division_id: str, heats_list: List[Dict[str, Any]]) -> None:
    heats = ensure_heats(db)
    heats[wod_id][division_id] = normalize_heats(copy.deepcopy(heats_list))
    save_db(db)


def current_layout(heats_list: List[Dict[str, Any]], athlete_count: int) -> List[int]:
    layout = [len(h.get("assignments", [])) for h in heats_list if len(h.get("assignments", [])) > 0]
    if layout:
        return layout

    if athlete_count <= 0:
        return [MAX_LANES]

    result: List[int] = []
    remaining = athlete_count
    while remaining > 0:
        take = min(MAX_LANES, remaining)
        result.append(take)
        remaining -= take
    return result or [MAX_LANES]


def parse_layout(layout_text: str) -> List[int]:
    raw = [x.strip() for x in str(layout_text).replace(";", ",").split(",")]
    result: List[int] = []

    for part in raw:
        if not part:
            continue
        size = int(part)
        if size < 1 or size > MAX_LANES:
            raise ValueError(f"Размер heat должен быть от 1 до {MAX_LANES}")
        result.append(size)

    if not result:
        raise ValueError("Укажи layout, например: 4,4,2")

    return result


def validate_layout_exact(layout: List[int], athlete_count: int) -> None:
    total_slots = sum(layout)
    if total_slots != athlete_count:
        raise ValueError(
            f"Layout должен точно совпадать с числом участников: "
            f"{athlete_count}. Сейчас в layout мест: {total_slots}."
        )


def flatten_athletes_from_heats(heats_list: List[Dict[str, Any]]) -> List[int]:
    athlete_ids: List[int] = []
    for heat in normalize_heats(heats_list):
        for assignment in sorted(heat.get("assignments", []), key=lambda x: x.get("lane", 0)):
            athlete_id = assignment.get("athlete_id")
            if athlete_id is not None and athlete_id not in athlete_ids:
                athlete_ids.append(int(athlete_id))
    return athlete_ids


def pack_into_heats(athlete_ids: List[int], layout: List[int]) -> List[Dict[str, Any]]:
    if len(athlete_ids) > sum(layout):
        raise ValueError("В layout не хватает мест для всех спортсменов")

    result: List[Dict[str, Any]] = []
    cursor = 0

    for heat_no, size in enumerate(layout, start=1):
        assignments = []
        for lane in range(1, size + 1):
            athlete_id = athlete_ids[cursor] if cursor < len(athlete_ids) else None
            if cursor < len(athlete_ids):
                cursor += 1
            assignments.append({"lane": lane, "athlete_id": athlete_id})
        result.append({"heat": heat_no, "assignments": assignments})

    return result


def option_ids(db: Dict[str, Any], division_id: str) -> List[Optional[int]]:
    ids: List[Optional[int]] = [None]
    for p in active_participants(db, division_id):
        try:
            ids.append(int(p["id"]))
        except (TypeError, ValueError, KeyError):
            continue
    return ids


def score_result_exists(db: Dict[str, Any], athlete_id: int, score_id: str) -> bool:
    results = db.get("results", {})
    athlete_results = results.get(str(athlete_id), {})
    return athlete_results.get(score_id) is not None


def required_previous_scores(wod_id: str) -> List[str]:
    if wod_id == "WOD2":
        return ["WOD1"]
    if wod_id == "WOD3":
        return ["WOD2A", "WOD2B"]
    return []


def previous_wod_label(wod_id: str) -> str:
    if wod_id == "WOD2":
        return "WOD1"
    if wod_id == "WOD3":
        return "WOD2A и WOD2B"
    return "предыдущий WOD"


def missing_required_results(db: Dict[str, Any], division_id: str, wod_id: str) -> List[Dict[str, Any]]:
    required_scores = required_previous_scores(wod_id)
    if not required_scores:
        return []

    missing: List[Dict[str, Any]] = []
    for p in active_participants(db, division_id):
        athlete_id = int(p["id"])
        missing_scores = [sid for sid in required_scores if not score_result_exists(db, athlete_id, sid)]
        if missing_scores:
            missing.append({"participant": p, "scores": missing_scores})
    return missing


def previous_heat_position(db: Dict[str, Any], prev_wod_id: str, division_id: str) -> Dict[int, Tuple[int, int]]:
    heats = get_division_heats(db, prev_wod_id, division_id)
    positions: Dict[int, Tuple[int, int]] = {}
    for heat in heats:
        heat_no = int(heat.get("heat") or 0)
        for assignment in heat.get("assignments", []):
            athlete_id = assignment.get("athlete_id")
            lane = int(assignment.get("lane") or 0)
            if athlete_id is None:
                continue
            positions[int(athlete_id)] = (heat_no, lane)
    return positions


def ranking_for_wod2(db: Dict[str, Any], division_id: str) -> List[int]:
    rows = build_ranking(db, division_id, "WOD1")
    pmap = participant_map(db)
    prev_positions = previous_heat_position(db, "WOD1", division_id)

    all_ids = [int(p["id"]) for p in active_participants(db, division_id)]
    rows_by_id = {int(r["athlete_id"]): r for r in rows}

    def sort_key(aid: int) -> Tuple[float, int, int, int, int]:
        row = rows_by_id.get(aid, {})
        points = float(row.get("points") or 0.0)
        prev_heat, prev_lane = prev_positions.get(aid, (999, 999))
        age = participant_age(pmap.get(aid) or {})
        age_value = int(age) if age is not None else -1
        return (
            points,
            -prev_heat,
            -age_value,
            prev_lane,
            aid,
        )

    return sorted(all_ids, key=sort_key)


def ranking_for_wod3(db: Dict[str, Any], division_id: str) -> List[int]:
    score_ids = ["WOD1", "WOD2A", "WOD2B"]
    totals: Dict[int, float] = {}
    pmap = participant_map(db)
    prev_positions = previous_heat_position(db, "WOD2", division_id)

    for sid in score_ids:
        for row in build_ranking(db, division_id, sid):
            athlete_id = int(row["athlete_id"])
            totals.setdefault(athlete_id, 0.0)
            pts = row.get("points")
            if pts is not None:
                totals[athlete_id] += float(pts)

    all_ids = [int(p["id"]) for p in active_participants(db, division_id)]
    for aid in all_ids:
        totals.setdefault(aid, 0.0)

    def sort_key(aid: int) -> Tuple[float, int, int, int, int]:
        prev_heat, prev_lane = prev_positions.get(aid, (999, 999))
        age = participant_age(pmap.get(aid) or {})
        age_value = int(age) if age is not None else -1
        return (
            totals.get(aid, 0.0),
            -prev_heat,
            -age_value,
            prev_lane,
            aid,
        )

    return sorted(all_ids, key=sort_key)


def duplicate_messages(heats_list: List[Dict[str, Any]], pmap: Dict[int, Dict[str, Any]]) -> List[str]:
    seen: Dict[int, str] = {}
    messages: List[str] = []

    for heat in normalize_heats(heats_list):
        for a in heat.get("assignments", []):
            athlete_id = a.get("athlete_id")
            if athlete_id is None:
                continue
            pos = f"heat {heat['heat']}, lane {a['lane']}"
            if athlete_id in seen:
                messages.append(f"{athlete_label(pmap.get(athlete_id))}: {seen[athlete_id]} и {pos}")
            else:
                seen[athlete_id] = pos

    return messages


def unassigned_athletes(db: Dict[str, Any], division_id: str, heats_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    assigned = set(flatten_athletes_from_heats(heats_list))
    return [p for p in active_participants(db, division_id) if int(p["id"]) not in assigned]


def build_current_values(
    key_prefix: str,
    normalized_source: List[Dict[str, Any]],
) -> Dict[Tuple[int, int], Optional[int]]:
    current_values: Dict[Tuple[int, int], Optional[int]] = {}

    for heat_idx, heat in enumerate(normalized_source):
        assignments_map = {a["lane"]: a.get("athlete_id") for a in heat.get("assignments", [])}
        size_default = max(1, len(heat.get("assignments", [])) or MAX_LANES)

        size_key = f"{key_prefix}_size_{heat_idx}"
        size = int(st.session_state.get(size_key, size_default))

        for lane in range(1, size + 1):
            widget_key = f"{key_prefix}_heat_{heat_idx}_lane_{lane}"
            if widget_key in st.session_state:
                current_pid = st.session_state.get(widget_key)
            else:
                current_pid = assignments_map.get(lane)

            if current_pid in ("", None):
                current_pid = None
            else:
                try:
                    current_pid = int(current_pid)
                except (TypeError, ValueError):
                    current_pid = None

            current_values[(heat_idx, lane)] = current_pid

    return current_values


def materialize_heats_from_session(key_prefix: str, source_heats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_source = normalize_heats(copy.deepcopy(source_heats))
    current_values = build_current_values(key_prefix, normalized_source)

    result: List[Dict[str, Any]] = []
    for heat_idx, heat in enumerate(normalized_source):
        size_default = max(1, len(heat.get("assignments", [])) or MAX_LANES)
        size_key = f"{key_prefix}_size_{heat_idx}"
        size = int(st.session_state.get(size_key, size_default))

        assignments: List[Dict[str, Any]] = []
        for lane in range(1, size + 1):
            assignments.append(
                {
                    "lane": lane,
                    "athlete_id": current_values.get((heat_idx, lane)),
                }
            )

        result.append({"heat": heat_idx + 1, "assignments": assignments})

    return normalize_heats(result)


def has_any_assigned_athletes(heats_list: List[Dict[str, Any]]) -> bool:
    for heat in normalize_heats(heats_list):
        for assignment in heat.get("assignments", []):
            if assignment.get("athlete_id") is not None:
                return True
    return False


def perform_autobuild(db: Dict[str, Any], wod_id: str, division_id: str, layout_text: str) -> Tuple[List[Dict[str, Any]], str]:
    layout = parse_layout(layout_text)

    if wod_id == "WOD1":
        athlete_ids = [int(p["id"]) for p in active_participants(db, division_id)]
        validate_layout_exact(layout, len(athlete_ids))
        random.shuffle(athlete_ids)
        generated = pack_into_heats(athlete_ids, layout)
        return generated, "WOD1 заполнен случайным образом"

    if wod_id == "WOD2":
        ranked_ids = ranking_for_wod2(db, division_id)
        validate_layout_exact(layout, len(ranked_ids))
        generated = pack_into_heats(ranked_ids, layout)
        return generated, "WOD2 собран по результатам WOD1: сильнейшие поставлены в поздние heats"

    if wod_id == "WOD3":
        ranked_ids = ranking_for_wod3(db, division_id)
        validate_layout_exact(layout, len(ranked_ids))
        generated = pack_into_heats(ranked_ids, layout)
        return generated, "WOD3 собран по сумме WOD1 + WOD2"

    raise ValueError("Неизвестный WOD для автосборки")


def render_editor(db: Dict[str, Any], division_id: str, heats_list: List[Dict[str, Any]], key_prefix: str) -> List[Dict[str, Any]]:
    pmap = participant_map(db)
    all_athlete_ids = option_ids(db, division_id)

    normalized_source = normalize_heats(heats_list)
    edited: List[Dict[str, Any]] = []
    cols = st.columns(max(1, min(4, len(normalized_source)))) if normalized_source else []

    current_values = build_current_values(key_prefix, normalized_source)

    for idx, heat in enumerate(normalized_source):
        col = cols[idx % len(cols)] if cols else st
        with col:
            with st.container(border=True):
                st.markdown(f"### Heat {idx + 1}")

                size_default = max(1, len(heat.get("assignments", [])) or MAX_LANES)
                size = st.number_input(
                    f"Размер heat {idx + 1}",
                    min_value=1,
                    max_value=MAX_LANES,
                    value=int(st.session_state.get(f"{key_prefix}_size_{idx}", size_default)),
                    step=1,
                    key=f"{key_prefix}_size_{idx}",
                )

                new_assignments: List[Dict[str, Any]] = []

                for lane in range(1, int(size) + 1):
                    current_pid = current_values.get((idx, lane))

                    used_elsewhere = set()
                    for (other_heat_idx, other_lane), other_pid in current_values.items():
                        if other_pid is None:
                            continue
                        if other_heat_idx == idx and other_lane == lane:
                            continue
                        used_elsewhere.add(other_pid)

                    lane_options: List[Optional[int]] = [None]
                    for athlete_id in all_athlete_ids:
                        if athlete_id is None:
                            continue
                        if athlete_id == current_pid or athlete_id not in used_elsewhere:
                            lane_options.append(athlete_id)

                    selected_index = lane_options.index(current_pid) if current_pid in lane_options else 0

                    selected_pid = st.selectbox(
                        f"{lane}. дорожка",
                        options=lane_options,
                        index=selected_index,
                        format_func=lambda pid, pmap=pmap: athlete_label(pmap.get(pid)) if pid is not None else "— пусто —",
                        key=f"{key_prefix}_heat_{idx}_lane_{lane}",
                    )

                    if selected_pid in ("", None):
                        selected_pid = None
                    else:
                        try:
                            selected_pid = int(selected_pid)
                        except (TypeError, ValueError):
                            selected_pid = None

                    current_values[(idx, lane)] = selected_pid
                    new_assignments.append({"lane": lane, "athlete_id": selected_pid})

                remove_col, move_col = st.columns(2)

                if remove_col.button(
                    "Удалить heat",
                    key=f"{key_prefix}_remove_{idx}",
                    type="secondary",
                    use_container_width=True,
                ):
                    current = materialize_heats_from_session(key_prefix, normalized_source)
                    smaller = [h for j, h in enumerate(current) if j != idx]
                    st.session_state[f"pending_heats::{key_prefix}"] = smaller
                    st.rerun()

                if move_col.button(
                    "Сделать последним",
                    key=f"{key_prefix}_move_{idx}",
                    use_container_width=True,
                ):
                    moved = materialize_heats_from_session(key_prefix, normalized_source)
                    item = moved.pop(idx)
                    moved.append(item)
                    st.session_state[f"pending_heats::{key_prefix}"] = moved
                    st.rerun()

                edited.append({"heat": idx + 1, "assignments": new_assignments})

    pending_key = f"pending_heats::{key_prefix}"
    if pending_key in st.session_state:
        pending = st.session_state.pop(pending_key)
        return normalize_heats(pending)

    return normalize_heats(edited)


def main() -> None:
    st.title("🏁 Heats")
    st.caption("Ручная настройка и автогенерация заходов для ТВ и телефона.")

    db = load_db()
    ensure_heats(db)

    title_map = division_title_map()
    division_ids = [d["id"] for d in DIVISIONS]

    top1, top2 = st.columns(2)
    selected_wod = top1.selectbox("Выбери WOD", HEAT_WODS, key="heats_wod")
    selected_division = top2.selectbox(
        "Выбери категорию",
        division_ids,
        format_func=lambda x: title_map.get(x, x),
        key="heats_division",
    )

    key_prefix = f"{selected_wod}_{selected_division}"
    draft_key = f"draft_heats::{key_prefix}"

    db_heats = get_division_heats(db, selected_wod, selected_division)

    if draft_key not in st.session_state:
        st.session_state[draft_key] = copy.deepcopy(db_heats)

    if f"pending_heats::{key_prefix}" in st.session_state:
        st.session_state[draft_key] = normalize_heats(
            copy.deepcopy(st.session_state.pop(f"pending_heats::{key_prefix}"))
        )

    working_heats = normalize_heats(copy.deepcopy(st.session_state[draft_key]))

    athletes = active_participants(db, selected_division)
    pmap = participant_map(db)
    layout_default = ",".join(str(x) for x in current_layout(working_heats, len(athletes)))

    st.write(f"Спортсменов в категории: **{len(athletes)}**")

    control1, control2 = st.columns([2, 3])

    with control1:
        layout_text = st.text_input(
            "Layout heats",
            value=layout_default,
            help="Например: 4,3 или 3,2,2",
            key=f"layout_{key_prefix}",
        )
        st.caption("Сумма мест должна точно совпадать с количеством участников. Максимум 4 дорожки в heat.")

    with control2:
        st.markdown("**Автосборка**")
        a1, a2, a3 = st.columns(3)
        random_wod1 = a1.button("Случайно для WOD1", use_container_width=True)
        auto_wod2 = a2.button("Собрать WOD2 по WOD1", use_container_width=True)
        auto_wod3 = a3.button("Собрать WOD3 по сумме", use_container_width=True)

        b1, b2, b3 = st.columns(3)
        apply_layout = b1.button("Применить layout", use_container_width=True)
        add_heat = b2.button("Добавить heat", use_container_width=True)
        reset_from_db = b3.button("Сбросить из базы", use_container_width=True)

    if reset_from_db:
        st.session_state[draft_key] = copy.deepcopy(db_heats)
        st.rerun()

    if add_heat:
        base = materialize_heats_from_session(key_prefix, working_heats) if working_heats else []
        base = normalize_heats(copy.deepcopy(base))
        base.append(
            {
                "heat": len(base) + 1,
                "assignments": [],
            }
        )
        st.session_state[draft_key] = normalize_heats(base)
        st.rerun()

    requested_auto: Optional[str] = None
    if random_wod1:
        requested_auto = "WOD1"
    elif auto_wod2:
        requested_auto = "WOD2"
    elif auto_wod3:
        requested_auto = "WOD3"

    if requested_auto in {"WOD2", "WOD3"}:
        missing_prev = missing_required_results(db, selected_division, requested_auto)
        if missing_prev:
            st.error(
                f"Автосборка {requested_auto} недоступна: не у всех атлетов заполнены результаты для {previous_wod_label(requested_auto)}."
            )
            for item in missing_prev:
                st.write(f"- {athlete_label(item['participant'])}: нет {', '.join(item['scores'])}")
            requested_auto = None

    if requested_auto:
        current_target_heats = get_division_heats(db, requested_auto, selected_division)
        if has_any_assigned_athletes(current_target_heats):
            st.session_state[AUTO_REQUEST_KEY] = {
                "wod_id": requested_auto,
                "division_id": selected_division,
                "layout_text": layout_text,
                "message": f"У категории {title_map.get(selected_division, selected_division)} уже есть heats для {requested_auto}. Автосборка перезапишет их полностью.",
            }
        else:
            try:
                generated, success_message = perform_autobuild(db, requested_auto, selected_division, layout_text)
                st.session_state[f"draft_heats::{requested_auto}_{selected_division}"] = normalize_heats(copy.deepcopy(generated))
                save_division_heats(db, requested_auto, selected_division, generated)
                st.success(success_message)
                if requested_auto == selected_wod:
                    st.session_state[draft_key] = normalize_heats(copy.deepcopy(generated))
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    pending_auto = st.session_state.get(AUTO_REQUEST_KEY)
    if isinstance(pending_auto, dict):
        if pending_auto.get("division_id") == selected_division:
            st.warning(str(pending_auto.get("message") or "Автосборка перезапишет текущие heats."))
            c1, c2 = st.columns(2)
            if c1.button("Подтвердить перезапись heats", key=f"confirm_auto_{selected_division}_{selected_wod}", type="primary", use_container_width=True):
                st.session_state[AUTO_CONFIRM_KEY] = pending_auto
                st.session_state.pop(AUTO_REQUEST_KEY, None)
                st.rerun()
            if c2.button("Отмена", key=f"cancel_auto_{selected_division}_{selected_wod}", use_container_width=True):
                st.session_state.pop(AUTO_REQUEST_KEY, None)
                st.session_state.pop(AUTO_CONFIRM_KEY, None)
                st.rerun()
        else:
            st.info("Есть ожидающая автосборка для другой категории. Вернись в неё и подтверди или отмени перезапись.")

    confirmed_auto = st.session_state.pop(AUTO_CONFIRM_KEY, None)
    if isinstance(confirmed_auto, dict):
        try:
            generated, success_message = perform_autobuild(
                db,
                str(confirmed_auto["wod_id"]),
                str(confirmed_auto["division_id"]),
                str(confirmed_auto["layout_text"]),
            )
            confirmed_key = f"draft_heats::{confirmed_auto['wod_id']}_{confirmed_auto['division_id']}"
            st.session_state[confirmed_key] = normalize_heats(copy.deepcopy(generated))
            save_division_heats(db, str(confirmed_auto["wod_id"]), str(confirmed_auto["division_id"]), generated)
            if str(confirmed_auto["wod_id"]) == selected_wod and str(confirmed_auto["division_id"]) == selected_division:
                st.session_state[draft_key] = normalize_heats(copy.deepcopy(generated))
            st.success(success_message)
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    try:
        if apply_layout:
            layout = parse_layout(layout_text)
            ordered = flatten_athletes_from_heats(materialize_heats_from_session(key_prefix, working_heats))
            if not ordered:
                ordered = [int(p["id"]) for p in athletes]
            validate_layout_exact(layout, len(ordered))
            generated = pack_into_heats(ordered, layout)
            st.session_state[draft_key] = normalize_heats(copy.deepcopy(generated))
            st.rerun()

    except ValueError as e:
        st.error(str(e))

    st.divider()
    st.subheader("Редактирование heats")

    if not working_heats:
        st.warning("Для этой категории пока нет заходов. Нажми «Добавить heat» или используй автосборку.")
        edited_heats: List[Dict[str, Any]] = []
    else:
        edited_heats = render_editor(db, selected_division, working_heats, key_prefix)
        st.session_state[draft_key] = normalize_heats(copy.deepcopy(edited_heats))

    duplicates = duplicate_messages(edited_heats, pmap)
    if duplicates:
        st.error("Есть дубли спортсменов внутри выбранных heats.")
        for msg in duplicates:
            st.write(f"- {msg}")
    else:
        st.success("Дубликатов внутри выбранных heats нет.")

    missing = unassigned_athletes(db, selected_division, edited_heats)
    if missing:
        st.warning("Не распределены по heats:")
        for p in missing:
            st.write(f"- {athlete_label(p)}")
    else:
        st.info("Все спортсмены этой категории распределены по heats.")

    s1, s2 = st.columns([1, 1])
    if s1.button("Сохранить текущие изменения", type="primary", use_container_width=True):
        save_division_heats(db, selected_wod, selected_division, edited_heats)
        st.session_state[draft_key] = normalize_heats(copy.deepcopy(edited_heats))
        st.success("Heats сохранены")
        st.rerun()

    if s2.button("Показать JSON этой категории", use_container_width=True):
        st.json(edited_heats)

    st.divider()
    st.subheader("Предпросмотр")

    if edited_heats:
        preview_cols = st.columns(max(1, min(4, len(edited_heats))))
        for idx, heat in enumerate(edited_heats):
            col = preview_cols[idx % len(preview_cols)]
            with col:
                with st.container(border=True):
                    st.markdown(f"**Heat {heat['heat']}**")
                    for a in sorted(heat.get("assignments", []), key=lambda x: x.get("lane", 0)):
                        lane = a.get("lane")
                        athlete_id = a.get("athlete_id")
                        label = athlete_label(pmap.get(athlete_id)) if athlete_id is not None else "— пусто —"
                        st.write(f"**{lane}.** {label}")
    else:
        st.caption("Пока нечего показывать.")


if __name__ == "__main__":
    main()
