import streamlit as st
import subprocess

st.set_page_config(page_title="Publish", layout="wide")
st.title("🚀 Publish (GitHub Pages)")

st.write(
    "Эта страница:\n"
    "1) Сгенерирует public/results.json и public/flags\n"
    "2) Сделает git add/commit/push\n"
)

if st.button("🚀 Publish now"):
    try:
        # вызываем publish/github_push.py как отдельный процесс
        subprocess.check_call("python -m publish.github_push", shell=True)
        st.success("Опубликовано. GitHub Pages обновится через несколько секунд/минуту.")
    except subprocess.CalledProcessError as e:
        st.error("Ошибка публикации. Проверь git (remote/доступ) и выведи сюда текст ошибки.")