import streamlit as st
import subprocess

st.set_page_config(page_title="Publish", layout="wide")
st.title("🚀 Publish (GitHub Pages)")

st.write(
    "Эта страница:\n"
    "1) Сгенерирует docs/results.json и docs/flags\n"
    "2) Сделает git add/commit/push\n"
)

if st.button("🚀 Publish now"):
    try:
        out = subprocess.check_output(
            "python -m publish.github_push",
            shell=True,
            stderr=subprocess.STDOUT,
            text=True,
        )
        st.success("Опубликовано. GitHub Pages обновится через несколько секунд/минуту.")
        st.code(out)
    except subprocess.CalledProcessError as e:
        st.error("Ошибка публикации. Вот вывод команды:")
        st.code(e.output)