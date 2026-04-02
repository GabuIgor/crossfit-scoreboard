import pandas as pd
import streamlit as st

from storage import load_db, save_db
from config import DIVISIONS
from utils import compact_page_style, parse_time_to_seconds, format_time_input_value

st.set_page_config(page_title="Ввод результатов", layout="wide")
compact_page_style()
st.title("🧾 Ввод результатов")

db = load_db()
settings = db["settings"]
scores = settings["scores"]

div_titles = {d["title"]: d["id"] for d in DIVISIONS}
score_titles = {f"{s['id']} — {s['title']}": s["id"] for s in scores}
STATUS_LABELS = {"ok": "Зачтено", "capped": "CAP", "wd": "Снялся"}
STATUS_CODES = {v: k for k, v in STATUS_LABELS.items()}

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
    label = f"{p['full_name']} ({p.get('club','')}, {region}) [ID:{p['id']}]"
    options.append(label)
    id_by_label[label] = int(p["id"])

st.subheader("Ввод результата через форму")
ath_label = st.selectbox("Атлет", options)
ath_id = id_by_label[ath_label]
current_result = db.get("results", {}).get(str(ath_id), {}).get(score_id, {})

col1, col2 = st.columns(2)
with col1:
    withdrawn = st.checkbox("Снялся", value=current_result.get("status") == "wd")
with col2:
    capped = st.checkbox("CAP", value=current_result.get("status") == "capped", disabled=not (stype == "time" and cap_enabled or withdrawn))

if withdrawn:
    capped = False

disabled_input = withdrawn or (stype == "time" and capped and cap_enabled)
value = None
if stype == "time":
    default_time = format_time_input_value(current_result.get("value")) if current_result.get("status") == "ok" else ""
    value = st.text_input("Время (мм:сс)", value=default_time, disabled=disabled_input, placeholder="например 8:34")
elif stype == "reps":
    value = st.number_input("Повторы", min_value=0, step=1, value=int(current_result.get("value") or 0), disabled=disabled_input)
elif stype == "weight":
    value = st.number_input("Вес (кг)", min_value=0.0, step=0.5, value=float(current_result.get("value") or 0.0), disabled=disabled_input)

if st.button("✅ Ввести результат", type="primary"):
    db.setdefault("results", {})
    db["results"].setdefault(str(ath_id), {})

    if withdrawn:
        db["results"][str(ath_id)][score_id] = {"status": "wd", "value": 0}
    elif stype == "time" and capped and cap_enabled:
        db["results"][str(ath_id)][score_id] = {"status": "capped", "value": None}
    else:
        if stype == "time":
            seconds = parse_time_to_seconds(value)
            if seconds is None:
                st.error("Для time укажи время в формате мм:сс, например 7:45.")
                st.stop()
            db["results"][str(ath_id)][score_id] = {"status": "ok", "value": int(seconds)}
        elif stype == "reps":
            db["results"][str(ath_id)][score_id] = {"status": "ok", "value": int(value)}
        else:
            db["results"][str(ath_id)][score_id] = {"status": "ok", "value": float(value)}

    save_db(db)
    st.success("Результат сохранён.")
    st.rerun()

st.divider()
st.subheader("Ввод результата через таблицу")

status_options = ["Зачтено", "Снялся"]
if stype == "time" and cap_enabled:
    status_options = ["Зачтено", "CAP", "Снялся"]

rows = []
for p in participants:
    res = db.get("results", {}).get(str(p["id"]), {}).get(score_id)
    raw_status = (res or {}).get("status", "ok")
    raw_value = (res or {}).get("value", None)
    if stype == "time" and raw_status == "ok":
        value_display = format_time_input_value(raw_value)
    elif raw_status == "capped":
        value_display = ""
    else:
        value_display = raw_value
    rows.append({
        "athlete_id": int(p["id"]),
        "athlete": p.get("full_name", ""),
        "club": p.get("club", ""),
        "region": p.get("region", "") or p.get("city", ""),
        "status": STATUS_LABELS.get(raw_status, "Зачтено"),
        "value": value_display,
    })

editor_df = pd.DataFrame(rows)
edited_df = st.data_editor(
    editor_df,
    use_container_width=True,
    hide_index=True,
    disabled=["athlete_id", "athlete", "club", "region"],
    column_config={
        "athlete_id": st.column_config.NumberColumn("ID", format="%d"),
        "athlete": st.column_config.TextColumn("Атлет"),
        "club": st.column_config.TextColumn("Клуб"),
        "region": st.column_config.TextColumn("Регион"),
        "status": st.column_config.SelectboxColumn("Статус", options=status_options, required=True),
        "value": st.column_config.TextColumn("Значение" if stype != "time" else "Время (мм:сс)"),
    },
    key=f"results_editor_{division_id}_{score_id}",
)

if st.button("💾 Сохранить таблицу результатов"):
    db.setdefault("results", {})
    for _, row in edited_df.iterrows():
        athlete_id = int(row["athlete_id"])
        status_display = str(row["status"] or "Зачтено")
        status = STATUS_CODES.get(status_display, "ok")
        raw_value = row["value"]

        db["results"].setdefault(str(athlete_id), {})

        if status == "wd":
            db["results"][str(athlete_id)][score_id] = {"status": "wd", "value": 0}
            continue
        if status == "capped":
            db["results"][str(athlete_id)][score_id] = {"status": "capped", "value": None}
            continue

        if pd.isna(raw_value) or raw_value in ("", None):
            db["results"][str(athlete_id)].pop(score_id, None)
            continue

        if stype == "time":
            seconds = parse_time_to_seconds(raw_value)
            if seconds is None:
                st.error(f"У атлета ID {athlete_id} неверный формат времени. Используй мм:сс.")
                st.stop()
            value_to_save = int(seconds)
        elif stype == "weight":
            value_to_save = float(raw_value)
        else:
            value_to_save = int(float(raw_value))

        db["results"][str(athlete_id)][score_id] = {"status": status, "value": value_to_save}

    save_db(db)
    st.success("Таблица результатов сохранена.")
    st.rerun()
