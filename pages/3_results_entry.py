import pandas as pd
import streamlit as st

from storage import load_db, save_db
from config import DIVISIONS
from utils import compact_page_style

st.set_page_config(page_title="Results Entry", layout="wide")
compact_page_style()
st.title("🧾 Results Entry")

db = load_db()
settings = db["settings"]
scores = settings["scores"]

div_titles = {d["title"]: d["id"] for d in DIVISIONS}
score_titles = {f"{s['id']} — {s['title']}": s["id"] for s in scores}

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

col1, col2 = st.columns(2)
with col1:
    withdrawn = st.checkbox("Снялся (0 очков)", value=False)
with col2:
    capped = st.checkbox("Не уложился (только для time)", value=False, disabled=not (stype == "time" and cap_enabled))

disabled_input = withdrawn
value = None
if stype == "time":
    if capped and cap_enabled:
        value = st.number_input("Повторы при time cap", min_value=0, step=1, value=0, disabled=disabled_input)
    else:
        value = st.number_input("Время (секунды)", min_value=0, step=1, value=0, disabled=disabled_input)
elif stype == "reps":
    value = st.number_input("Повторы", min_value=0, step=1, value=0, disabled=disabled_input)
elif stype == "weight":
    value = st.number_input("Вес (кг)", min_value=0.0, step=0.5, value=0.0, disabled=disabled_input)

if st.button("✅ Ввести результат", type="primary"):
    db.setdefault("results", {})
    db["results"].setdefault(str(ath_id), {})

    if withdrawn:
        db["results"][str(ath_id)][score_id] = {"status": "wd", "value": 0}
    else:
        if stype == "time" and capped and cap_enabled:
            db["results"][str(ath_id)][score_id] = {"status": "capped", "value": int(value)}
        else:
            if stype in ("time", "reps"):
                db["results"][str(ath_id)][score_id] = {"status": "ok", "value": int(value)}
            else:
                db["results"][str(ath_id)][score_id] = {"status": "ok", "value": float(value)}

    save_db(db)
    st.success("Результат сохранён.")

st.divider()
st.subheader("Ввод результата через таблицу")
st.caption("В Streamlit редактирование идёт через клик по ячейке. Это почти тот же сценарий, что и двойной щелчок в таблице.")

status_options = ["ok", "wd"]
if stype == "time" and cap_enabled:
    status_options = ["ok", "capped", "wd"]

rows = []
for p in participants:
    res = db.get("results", {}).get(str(p["id"]), {}).get(score_id)
    rows.append({
        "athlete_id": int(p["id"]),
        "athlete": p.get("full_name", ""),
        "club": p.get("club", ""),
        "region": p.get("region", "") or p.get("city", ""),
        "status": (res or {}).get("status", "ok"),
        "value": (res or {}).get("value", None),
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
        "value": st.column_config.NumberColumn("Значение", step=0.5 if stype == "weight" else 1),
    },
    key=f"results_editor_{division_id}_{score_id}",
)

if st.button("💾 Сохранить таблицу результатов"):
    db.setdefault("results", {})
    for _, row in edited_df.iterrows():
        athlete_id = int(row["athlete_id"])
        status = str(row["status"] or "ok")
        raw_value = row["value"]

        if status not in status_options:
            status = "ok"

        db["results"].setdefault(str(athlete_id), {})

        if status == "wd":
            db["results"][str(athlete_id)][score_id] = {"status": "wd", "value": 0}
            continue

        if pd.isna(raw_value) or raw_value in ("", None):
            db["results"][str(athlete_id)].pop(score_id, None)
            continue

        if stype == "weight":
            value_to_save = float(raw_value)
        else:
            value_to_save = int(float(raw_value))

        db["results"][str(athlete_id)][score_id] = {"status": status, "value": value_to_save}

    save_db(db)
    st.success("Таблица результатов сохранена.")
