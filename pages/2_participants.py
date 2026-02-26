import streamlit as st
from PIL import Image
from io import BytesIO

from storage import load_db, save_db, next_participant_id, count_participants_in_division, delete_participant
from config import DIVISIONS, DATA_FLAGS_DIR

st.set_page_config(page_title="Participants", layout="wide")
st.title("👥 Participants")

db = load_db()

# --- форма добавления ---
st.subheader("Добавить участника")

with st.form("add_participant"):
    full_name = st.text_input("Фамилия Имя")
    sex = st.selectbox("Пол", ["M", "F"])
    age = st.number_input("Возраст", min_value=1, max_value=120, step=1, value=25)
    category = st.selectbox("Категория", ["BEGSCAL", "INT"])
    city = st.text_input("Город")
    club = st.text_input("Клуб")

    # Флаг — загружаем картинку
    flag_file = st.file_uploader("Флаг (PNG/JPG). Рекомендую 3:2 или 4:3", type=["png", "jpg", "jpeg"])

    submitted = st.form_submit_button("➕ Добавить")

def resolve_division_id(sex_val: str, cat_val: str) -> str:
    # по твоей логике: категория + пол = дивизион
    if cat_val == "BEGSCAL" and sex_val == "M":
        return "BEGSCAL_M"
    if cat_val == "BEGSCAL" and sex_val == "F":
        return "BEGSCAL_F"
    if cat_val == "INT" and sex_val == "M":
        return "INT_M"
    return "INT_F"

if submitted:
    name = (full_name or "").strip()
    if not name:
        st.error("ФИО пустое.")
    else:
        division_id = resolve_division_id(sex, category)

        # лимит участников
        limit = int(db["settings"]["division_limits"].get(division_id, 0))
        current = count_participants_in_division(db, division_id)
        if limit > 0 and current >= limit:
            st.error(f"Лимит для {division_id} = {limit}. Сейчас уже {current}. Добавление запрещено.")
        else:
            pid = next_participant_id(db)

            flag_path = None
            if flag_file is not None:
                # сохраняем флаг в data/flags как athlete_<id>.png
                img_bytes = flag_file.read()
                try:
                    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
                    out_path = DATA_FLAGS_DIR / f"athlete_{pid}.png"
                    img.save(out_path, format="PNG")
                    flag_path = str(out_path.as_posix())
                except Exception as e:
                    st.error(f"Не удалось обработать картинку флага: {e}")

            db["participants"].append({
                "id": pid,
                "full_name": name,
                "sex": sex,
                "age": int(age),
                "category": category,
                "division_id": division_id,
                "city": (city or "").strip(),
                "club": (club or "").strip(),
                "flag_path": flag_path,  # путь на локальный файл
                "deleted": False,
            })

            save_db(db)
            st.success(f"Добавлен: {name} → {division_id}")
            st.rerun()

st.divider()

# --- список + удаление с подтверждением ---
st.subheader("Список участников (удаление с подтверждением)")

participants = [p for p in db.get("participants", []) if not p.get("deleted", False)]

if not participants:
    st.info("Пока участников нет.")
else:
    # храним "кто ждёт подтверждения удаления"
    if "pending_delete_id" not in st.session_state:
        st.session_state.pending_delete_id = None

    header = st.columns([1, 3, 1, 1, 2, 2, 1, 1])
    header[0].markdown("**ID**")
    header[1].markdown("**ФИО**")
    header[2].markdown("**Пол**")
    header[3].markdown("**Возраст**")
    header[4].markdown("**DIV**")
    header[5].markdown("**Клуб**")
    header[6].markdown("**Флаг**")
    header[7].markdown("**Del**")

    for p in participants:
        cols = st.columns([1, 3, 1, 1, 2, 2, 1, 1])
        cols[0].write(p["id"])
        cols[1].write(p.get("full_name", ""))
        cols[2].write(p.get("sex", ""))
        cols[3].write(p.get("age", ""))
        cols[4].write(p.get("division_id", ""))
        cols[5].write(p.get("club", ""))

        # показываем флаг как маленькую картинку (если есть)
        fp = p.get("flag_path")
        if fp:
            try:
                cols[6].image(fp, width=40)
            except Exception:
                cols[6].write("⚠️")

        # кнопка удаления
        if cols[7].button("❌", key=f"del_{p['id']}"):
            st.session_state.pending_delete_id = int(p["id"])

    # блок подтверждения удаления
    if st.session_state.pending_delete_id is not None:
        pid = st.session_state.pending_delete_id
        target = next((x for x in participants if int(x["id"]) == int(pid)), None)
        if target:
            st.warning(f"Удалить участника: **{target['full_name']}** (ID {pid}) ?")
            c1, c2 = st.columns(2)
            if c1.button("✅ Да, удалить"):
                delete_participant(db, pid)
                save_db(db)
                st.session_state.pending_delete_id = None
                st.success("Удалено.")
                st.rerun()
            if c2.button("❌ Нет, отмена"):
                st.session_state.pending_delete_id = None
                st.info("Отменено.")
        else:
            st.session_state.pending_delete_id = None