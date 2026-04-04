import re

import pandas as pd
import streamlit as st

from storage import load_db, save_db
from config import DIVISIONS
from utils import compact_page_style, parse_time_mmss, format_time_mmss, display_result_value

st.set_page_config(page_title="Results Entry", layout="wide")
compact_page_style()
st.title("🧾 Results Entry")


db = load_db()
settings = db["settings"]
scores = settings["scores"]

div_titles = {d["title"]: d["id"] for d in DIVISIONS}
score_titles = {f"{s['id']} — {s['title']}": s["id"] for s in scores}
STATUS_LABELS = {"ok": "Зачтено", "capped": "CAP", "wd": "Снялся"}
LABEL_TO_STATUS = {v: k for k, v in STATUS_LABELS.items()}
TIME_RE = re.compile(r"^\d+:\d{2}$")


def display_result_for_entry(score_def, res):
    if res is None:
        return ""
    status = res.get("status")
    value = res.get("value")
    if status == "wd":
        return "Снялся"
    if status == "capped":
        reps_text = display_result_value({"type": "reps"}, value)
        return f"CAP {reps_text}" if reps_text else "CAP"
    return display_result_value(score_def, value)


def normalize_time_input(value):
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    total = parse_time_mmss(raw)
    if total is None:
        return None
    pretty = format_time_mmss(total)
    if not TIME_RE.match(pretty):
        return None
    return pretty


colA, colB = st.columns(2)
with colA:
    div_label = st.selectbox("Дивизион", list(div_titles.keys()))
    division_id = div_titles[div_label]
with colB:
    score_label = st.selectbox("Зачёт / Комплекс", list(score_titles.keys()))
    score_id = score_titles[score_label]

sdef = next(s for s in scores if s["id"] == score_id)
stype = sdef["type"]
cap_enabled = bool(sdef.get("time_cap_enabled", False))

st.info(f"Тип зачёта: **{stype}**. Time cap: **{cap_enabled}**")

participants = [
    p for p in db.get("participants", [])
    if p.get("division_id") == division_id and not p.get("deleted", False)
]
participants.sort(key=lambda p: (p.get("full_name") or "").lower())

if not participants:
    st.warning("В этом дивизионе нет участников.")
    st.stop()

options = []
id_by_label = {}
for p in participants:
    region = p.get("region", "") or p.get("city", "")
    label = f"{p['full_name']} ({p.get('club', '')}, {region}) [ID:{p['id']}]"
    options.append(label)
    id_by_label[label] = int(p["id"])

st.subheader("Ввод результата через форму")
ath_label = st.selectbox("Атлет", options)
ath_id = id_by_label[ath_label]
existing = db.get("results", {}).get(str(ath_id), {}).get(score_id) or {}
existing_time = format_time_mmss(existing.get("value")) if existing.get("status") == "ok" and stype == "time" else ""

with st.form(key=f"single_result_form_{division_id}_{score_id}_{ath_id}"):
    col1, col2 = st.columns(2)
    with col1:
        withdrawn = st.checkbox("Снялся", value=existing.get("status") == "wd")
    with col2:
        capped = st.checkbox(
            "CAP",
            value=existing.get("status") == "capped",
            disabled=not (stype == "time" and cap_enabled),
        )

    disabled_input = withdrawn
    value = None
    raw_time_value = ""

    if stype == "time":
        if capped and cap_enabled:
            value = st.number_input(
                "Повторы при CAP",
                min_value=0,
                step=1,
                value=int(existing.get("value") or 0) if existing.get("status") == "capped" else 0,
                disabled=disabled_input,
            )
            st.caption("Для CAP время не вводится — только повторения.")
        else:
            raw_time_value = st.text_input(
                "Время",
                value=existing_time,
                placeholder="00:00",
                disabled=disabled_input,
                help="Строго в формате мм:сс. Например: 05:34 или 12:08",
            )
            preview_time = normalize_time_input(raw_time_value)
            if raw_time_value and preview_time is None:
                st.caption("Вводи только в формате мм:сс. Например: 05:34")
            else:
                st.caption(f"Формат: мм:сс{f' · будет сохранено как {preview_time}' if preview_time else ''}")
    elif stype == "reps":
        value = st.number_input(
            "Повторы",
            min_value=0,
            step=1,
            value=int(existing.get("value") or 0) if existing.get("status") == "ok" else 0,
            disabled=disabled_input,
        )
    elif stype == "weight":
        value = st.number_input(
            "Вес (кг)",
            min_value=0.0,
            step=0.5,
            value=float(existing.get("value") or 0.0) if existing.get("status") == "ok" else 0.0,
            disabled=disabled_input,
        )

    submitted_single = st.form_submit_button("✅ Ввести результат", type="primary")

if submitted_single:
    db.setdefault("results", {})
    db["results"].setdefault(str(ath_id), {})

    if withdrawn:
        db["results"][str(ath_id)][score_id] = {"status": "wd", "value": 0}
    else:
        if stype == "time" and capped and cap_enabled:
            db["results"][str(ath_id)][score_id] = {"status": "capped", "value": int(value)}
        else:
            if stype == "time":
                normalized = normalize_time_input(raw_time_value)
                if normalized is None:
                    st.error("Для TIME введи значение строго в формате мм:сс. Например: 05:34")
                    st.stop()
                db["results"][str(ath_id)][score_id] = {"status": "ok", "value": int(parse_time_mmss(normalized))}
            elif stype == "reps":
                db["results"][str(ath_id)][score_id] = {"status": "ok", "value": int(value)}
            else:
                db["results"][str(ath_id)][score_id] = {"status": "ok", "value": float(value)}

    save_db(db)
    st.success("Результат сохранён.")
    st.rerun()

st.divider()
st.subheader("Ввод результата через таблицу")
if stype == "time":
    st.caption("TIME вводится одной строкой строго в формате мм:сс. Например: 05:34")

status_options = [STATUS_LABELS["ok"], STATUS_LABELS["wd"]]
if stype == "time" and cap_enabled:
    status_options = [STATUS_LABELS["ok"], STATUS_LABELS["capped"], STATUS_LABELS["wd"]]

rows = []
for p in participants:
    res = db.get("results", {}).get(str(p["id"]), {}).get(score_id)
    display_value = None
    if res is not None:
        if stype == "time" and res.get("status") == "ok":
            display_value = format_time_mmss(res.get("value"))
        else:
            display_value = res.get("value", None)
    rows.append({
        "athlete_id": int(p["id"]),
        "athlete": p.get("full_name", ""),
        "club": p.get("club", ""),
        "region": p.get("region", "") or p.get("city", ""),
        "status": STATUS_LABELS.get((res or {}).get("status", "ok"), "Зачтено"),
        "value": display_value,
        "preview": display_result_for_entry(sdef, res),
    })

editor_df = pd.DataFrame(rows)
value_column = st.column_config.NumberColumn("Значение", step=0.5 if stype == "weight" else 1)
if stype == "time":
    value_column = st.column_config.TextColumn("Время")
elif stype == "time" and cap_enabled:
    value_column = st.column_config.TextColumn("Время / повторы")

with st.form(key=f"results_table_form_{division_id}_{score_id}"):
    edited_df = st.data_editor(
        editor_df,
        width="stretch",
        hide_index=True,
        disabled=["athlete_id", "athlete", "club", "region", "preview"],
        column_config={
            "athlete_id": st.column_config.NumberColumn("ID", format="%d"),
            "athlete": st.column_config.TextColumn("Атлет"),
            "club": st.column_config.TextColumn("Клуб"),
            "region": st.column_config.TextColumn("Регион"),
            "status": st.column_config.SelectboxColumn("Статус", options=status_options, required=True),
            "value": value_column,
            "preview": st.column_config.TextColumn("Будет показано"),
        },
        key=f"results_editor_{division_id}_{score_id}",
    )
    submitted_table = st.form_submit_button("💾 Сохранить таблицу результатов")

if submitted_table:
    db.setdefault("results", {})
    errors = []

    for _, row in edited_df.iterrows():
        athlete_id = int(row["athlete_id"])
        athlete_name = str(row["athlete"] or athlete_id)
        status_label = str(row["status"] or "Зачтено")
        status = LABEL_TO_STATUS.get(status_label, "ok")
        raw_value = row["value"]

        db["results"].setdefault(str(athlete_id), {})

        if status == "wd":
            db["results"][str(athlete_id)][score_id] = {"status": "wd", "value": 0}
            continue

        if pd.isna(raw_value) or raw_value in ("", None):
            db["results"][str(athlete_id)].pop(score_id, None)
            continue

        if stype == "weight":
            value_to_save = float(raw_value)
        elif stype == "time":
            if status == "capped":
                try:
                    value_to_save = int(float(raw_value))
                except (TypeError, ValueError):
                    errors.append(f"{athlete_name}: для CAP введи целое число повторов")
                    continue
            else:
                normalized = normalize_time_input(raw_value)
                if normalized is None:
                    errors.append(f"{athlete_name}: время должно быть в формате мм:сс")
                    continue
                value_to_save = int(parse_time_mmss(normalized))
        else:
            value_to_save = int(float(raw_value))

        db["results"][str(athlete_id)][score_id] = {"status": status, "value": value_to_save}

    if errors:
        st.error("Не сохранил таблицу. Исправь ошибки:\n- " + "\n- ".join(errors[:12]))
        st.stop()

    save_db(db)
    st.success("Таблица результатов сохранена.")
    st.rerun()
