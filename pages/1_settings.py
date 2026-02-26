import streamlit as st
from storage import load_db, save_db
from config import DIVISIONS

st.set_page_config(page_title="Settings", layout="wide")
st.title("⚙️ Settings")

db = load_db()

st.subheader("Лимиты участников по дивизионам")

limits = db["settings"]["division_limits"]
changed = False

cols = st.columns(4)
for i, d in enumerate(DIVISIONS):
    with cols[i]:
        key = d["id"]
        cur = int(limits.get(key, 0))
        new_val = st.number_input(d["title"], min_value=0, step=1, value=cur, key=f"limit_{key}")
        if int(new_val) != cur:
            limits[key] = int(new_val)
            changed = True

st.divider()
st.subheader("Настройка зачётов (универсально)")

# Здесь можно менять тип зачёта, но пока оставим аккуратно.
score_rows = db["settings"]["scores"]
for s in score_rows:
    st.markdown(f"### {s['id']} — {s['title']}")
    c1, c2 = st.columns(2)
    with c1:
        new_type = st.selectbox(
            "Тип",
            ["time", "reps", "weight"],
            index=["time", "reps", "weight"].index(s["type"]),
            key=f"type_{s['id']}",
        )
        if new_type != s["type"]:
            s["type"] = new_type
            changed = True
    with c2:
        new_cap = st.checkbox("Разрешить Time cap (только для time)", value=bool(s.get("time_cap_enabled", False)), key=f"cap_{s['id']}")
        if new_cap != bool(s.get("time_cap_enabled", False)):
            s["time_cap_enabled"] = bool(new_cap)
            changed = True

st.divider()
if st.button("💾 Save Settings"):
    save_db(db)
    st.success("Сохранено.")
else:
    if changed:
        st.warning("Есть изменения. Нажми Save Settings.")