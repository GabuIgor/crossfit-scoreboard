import streamlit as st
from storage import load_db, save_db
from config import DIVISIONS

st.set_page_config(page_title="Heats", layout="wide")
st.title("🏁 Heats (каркас)")

db = load_db()

st.info(
    "Здесь будет управление заходами.\n"
    "Сейчас это каркас, чтобы структура проекта была готова.\n"
    "Следующим шагом сделаем: ручной WOD1 + авто WOD2/WOD3."
)

# Показываем текущую структуру heats (пока пусто)
st.subheader("Текущие данные heats в db.json")
st.json(db.get("heats", {}))

if st.button("💾 Сохранить (пока без изменений)"):
    save_db(db)
    st.success("Ок.")