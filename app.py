import streamlit as st

st.set_page_config(page_title="CrossFit Admin", layout="wide")

st.title("CrossFit — Админка (локально)")
st.write("Открой нужный раздел:")

st.page_link("pages/1_settings.py", label="⚙️ Settings", icon="⚙️")
st.page_link("pages/2_participants.py", label="👥 Participants", icon="👥")
st.page_link("pages/3_results_entry.py", label="🧾 Results Entry", icon="🧾")
st.page_link("pages/4_tables.py", label="📊 Tables", icon="📊")
st.page_link("pages/5_heats.py", label="🏁 Heats (каркас)", icon="🏁")
st.page_link("pages/6_publish.py", label="🚀 Publish (GitHub Pages)", icon="🚀")

st.divider()
st.info("Админка работает локально. Публичная витрина обновляется после кнопки Publish.")