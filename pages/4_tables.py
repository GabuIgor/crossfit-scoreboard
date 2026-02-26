import streamlit as st
from storage import load_db
from config import DIVISIONS
from scoring import build_ranking, total_points_for_athlete

st.set_page_config(page_title="Tables", layout="wide")
st.title("📊 Tables (админ-панель)")

db = load_db()
settings = db["settings"]
scores = settings["scores"]
score_ids = [s["id"] for s in scores]

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

# 2x2 расклад дивизионов
grid = [
    ["BEGSCAL_F", "INT_F"],
    ["BEGSCAL_M", "INT_M"],
]

for row in grid:
    c1, c2 = st.columns(2)
    for col, div_id in zip([c1, c2], row):
        div = next(d for d in DIVISIONS if d["id"] == div_id)
        with col:
            st.subheader(div["title"])

            # строим строки по участникам
            participants = [
                p for p in db.get("participants", [])
                if p.get("division_id") == div_id and not p.get("deleted", False)
            ]

            # для каждой строки считаем очки по каждому score_id через ranking
            # проще: заранее построим ranking map: athlete_id -> points
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
                    "Клуб": p.get("club", ""),
                    "Город": p.get("city", ""),
                }

                # Флаг отображаем как путь (в админке st.dataframe не покажет картинку).
                # Картинку мы показываем отдельно ниже по желанию.
                row["Флаг"] = "✅" if p.get("flag_path") else "—"

                # очки за зачёты + отображение результата рядом (чтобы админу было понятно)
                for s in scores:
                    sid = s["id"]
                    pts = points_maps[sid].get(aid)
                    res = result_maps[sid].get(aid)
                    # если нет результата -> "—"
                    if pts is None:
                        row[f"{sid}"] = "—"
                    else:
                        row[f"{sid}"] = pts

                    row[f"{sid}_res"] = display_value_for_public(s, res)

                row["ИТОГО"] = total_points_for_athlete(db, aid)
                table_rows.append(row)

            # сортировка по итого (чем больше, тем лучше)
            table_rows.sort(key=lambda r: (-(r["ИТОГО"]), r["ФИО"]))

            st.dataframe(table_rows, use_container_width=True, hide_index=True)

st.caption("Примечание: если результата нет — стоит '—' и он не участвует в сумме. WD = 0 очков.")