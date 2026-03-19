import streamlit as st
from storage import load_db
from config import DIVISIONS
from scoring import build_ranking, total_points_for_athlete
from utils import compact_page_style

st.set_page_config(page_title="Tables", layout="wide")
compact_page_style()
st.title("📊 Tables (админ-панель)")

db = load_db()
settings = db["settings"]
scores = settings["scores"]


def display_value_for_public(sdef, res):
    if res is None:
        return "—"
    status = res.get("status")
    val = res.get("value")
    if status == "wd":
        return "WD"
    if sdef["type"] == "time":
        if status == "ok":
            return f"{int(val)}s"
        if status == "capped":
            return f"CAP {int(val)} reps"
    return str(val)


for div in DIVISIONS:
    div_id = div["id"]
    st.subheader(div["title"])

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

    table_rows = []
    for p in participants:
        aid = int(p["id"])
        row = {
            "ФИО": p.get("full_name", ""),
            "Возраст": p.get("age", ""),
            "DIV": p.get("category", ""),
            "Регион": p.get("region", "") or p.get("city", ""),
            "Клуб": p.get("club", ""),
            "Флаг": "✅" if p.get("flag_path") else "—",
        }
        for s in scores:
            sid = s["id"]
            pts = points_maps[sid].get(aid)
            res = result_maps[sid].get(aid)
            row[f"{sid}"] = "—" if pts is None else pts
            row[f"{sid}_res"] = display_value_for_public(s, res)
        row["ИТОГО"] = total_points_for_athlete(db, aid)
        table_rows.append(row)

    table_rows.sort(key=lambda r: (-(r["ИТОГО"]), r["ФИО"]))
    st.dataframe(table_rows, use_container_width=True, hide_index=True)
    st.divider()

st.caption("Если результата нет — стоит '—' и он не участвует в сумме. WD = 0 очков.")
