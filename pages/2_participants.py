import streamlit as st
from PIL import Image
from io import BytesIO

from storage import load_db, save_db, next_participant_id, count_participants_in_division, delete_participant
from config import DATA_FLAGS_DIR, MAX_FLAG_UPLOAD_BYTES, MAX_FLAG_DIMENSION
from utils import compact_page_style

st.set_page_config(page_title="Participants", layout="wide")
compact_page_style()
st.title("👥 Participants")

db = load_db()


def resolve_division_id(sex_val: str, cat_val: str) -> str:
    if cat_val == "BEGSCAL" and sex_val == "M":
        return "BEGSCAL_M"
    if cat_val == "BEGSCAL" and sex_val == "F":
        return "BEGSCAL_F"
    if cat_val == "INT" and sex_val == "M":
        return "INT_M"
    return "INT_F"


def save_flag_image(flag_file, pid: int) -> str:
    img_bytes = flag_file.read()
    if len(img_bytes) > MAX_FLAG_UPLOAD_BYTES:
        max_mb = round(MAX_FLAG_UPLOAD_BYTES / 1024 / 1024, 2)
        raise ValueError(f"Файл флага слишком большой. Максимум {max_mb} MB.")

    try:
        img = Image.open(BytesIO(img_bytes))
        img.verify()
        img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    except Exception as exc:
        raise ValueError(f"Не удалось обработать картинку флага: {exc}") from exc

    img.thumbnail((MAX_FLAG_DIMENSION, MAX_FLAG_DIMENSION))
    out_path = DATA_FLAGS_DIR / f"athlete_{pid}.png"
    img.save(out_path, format="PNG", optimize=True)
    return str(out_path.as_posix())


st.subheader("Добавить участника")
with st.form("add_participant"):
    c1, c2, c3 = st.columns(3)
    with c1:
        full_name = st.text_input("Фамилия Имя")
        sex = st.selectbox("Пол", ["M", "F"])
        age = st.number_input("Возраст", min_value=1, max_value=120, step=1, value=25)
    with c2:
        category = st.selectbox("Категория", ["BEGSCAL", "INT"])
        region = st.text_input("Регион")
        city = st.text_input("Город")
    with c3:
        club = st.text_input("Клуб / команда")
        flag_file = st.file_uploader(
            f"Флаг (PNG/JPG, до {MAX_FLAG_UPLOAD_BYTES // 1024 // 1024} MB)",
            type=["png", "jpg", "jpeg"],
        )

    submitted = st.form_submit_button("➕ Добавить")

if submitted:
    name = (full_name or "").strip()
    if not name:
        st.error("ФИО пустое.")
    else:
        division_id = resolve_division_id(sex, category)
        limit = int(db["settings"]["division_limits"].get(division_id, 0))
        current = count_participants_in_division(db, division_id)

        if limit > 0 and current >= limit:
            st.error(f"Лимит для {division_id} = {limit}. Сейчас уже {current}. Добавление запрещено.")
        else:
            pid = next_participant_id(db)
            flag_path = None
            if flag_file is not None:
                try:
                    flag_path = save_flag_image(flag_file, pid)
                except ValueError as exc:
                    st.error(str(exc))
                    st.stop()

            db["participants"].append({
                "id": pid,
                "full_name": name,
                "sex": sex,
                "age": int(age),
                "category": category,
                "division_id": division_id,
                "region": (region or "").strip(),
                "city": (city or "").strip(),
                "club": (club or "").strip(),
                "flag_path": flag_path,
                "deleted": False,
            })

            save_db(db)
            st.success(f"Добавлен: {name} → {division_id}")
            st.rerun()

st.divider()
st.subheader("Список участников")
participants = [p for p in db.get("participants", []) if not p.get("deleted", False)]

if not participants:
    st.info("Пока участников нет.")
else:
    if "pending_delete_id" not in st.session_state:
        st.session_state.pending_delete_id = None

    header = st.columns([0.6, 2.5, 0.7, 0.8, 1.4, 1.4, 1.6, 1.0, 0.8])
    labels = ["ID", "ФИО", "Пол", "Возраст", "DIV", "Регион", "Клуб / команда", "Флаг", "Del"]
    for col, label in zip(header, labels):
        col.markdown(f"**{label}**")

    for p in participants:
        cols = st.columns([0.6, 2.5, 0.7, 0.8, 1.4, 1.4, 1.6, 1.0, 0.8])
        cols[0].write(p["id"])
        cols[1].write(p.get("full_name", ""))
        cols[2].write(p.get("sex", ""))
        cols[3].write(p.get("age", ""))
        cols[4].write(p.get("division_id", ""))
        cols[5].write(p.get("region", "") or p.get("city", ""))
        cols[6].write(p.get("club", ""))

        fp = p.get("flag_path")
        if fp:
            try:
                cols[7].image(fp, width=34)
            except Exception:
                cols[7].write("⚠️")
        else:
            cols[7].write("—")

        if cols[8].button("❌", key=f"del_{p['id']}"):
            st.session_state.pending_delete_id = int(p["id"])

    if st.session_state.pending_delete_id is not None:
        pid = st.session_state.pending_delete_id
        target = next((x for x in participants if int(x["id"]) == int(pid)), None)
        if target:
            st.warning(f"Удалить участника: **{target['full_name']}** (ID {pid})?")
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
