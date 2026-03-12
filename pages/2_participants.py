import os
from io import BytesIO

import streamlit as st
from PIL import Image

from storage import (
    count_participants_in_division,
    delete_participant,
    load_db,
    next_participant_id,
    save_db,
)
from config import DATA_FLAGS_DIR

MAX_FLAG_SIZE_BYTES = 1 * 1024 * 1024

st.set_page_config(page_title="Participants", layout="wide")
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


def save_flag_image(flag_file, participant_id: int) -> str:
    if flag_file is None:
        return None

    file_size = getattr(flag_file, "size", None)
    if file_size is not None and file_size > MAX_FLAG_SIZE_BYTES:
        raise ValueError("Файл флага слишком большой. Максимум 1 MB.")

    img_bytes = flag_file.read()
    if len(img_bytes) > MAX_FLAG_SIZE_BYTES:
        raise ValueError("Файл флага слишком большой. Максимум 1 MB.")

    try:
        img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    except Exception as exc:
        raise ValueError(f"Не удалось обработать картинку флага: {exc}") from exc

    out_path = DATA_FLAGS_DIR / f"athlete_{participant_id}.png"
    img.save(out_path, format="PNG")
    return str(out_path.as_posix())


if "pending_delete_id" not in st.session_state:
    st.session_state.pending_delete_id = None
if "pending_edit_id" not in st.session_state:
    st.session_state.pending_edit_id = None


# --- форма добавления ---
st.subheader("Добавить участника")

with st.form("add_participant"):
    c1, c2, c3 = st.columns(3)
    full_name = c1.text_input("Фамилия Имя")
    sex = c2.selectbox("Пол", ["M", "F"])
    age = c3.number_input("Возраст", min_value=1, max_value=120, step=1, value=25)

    c4, c5, c6 = st.columns(3)
    category = c4.selectbox("Категория", ["BEGSCAL", "INT"])
    city = c5.text_input("Город")
    club = c6.text_input("Клуб")

    region = st.text_input("Регион")
    flag_file = st.file_uploader(
        "Флаг (PNG/JPG). Рекомендую 3:2 или 4:3. Максимум 1 MB",
        type=["png", "jpg", "jpeg"],
        key="add_flag",
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
            try:
                flag_path = save_flag_image(flag_file, pid) if flag_file is not None else None
            except ValueError as exc:
                st.error(str(exc))
            else:
                db["participants"].append(
                    {
                        "id": pid,
                        "full_name": name,
                        "sex": sex,
                        "age": int(age),
                        "category": category,
                        "division_id": division_id,
                        "city": (city or "").strip(),
                        "club": (club or "").strip(),
                        "region": (region or "").strip(),
                        "flag_path": flag_path,
                        "deleted": False,
                    }
                )

                save_db(db)
                st.success(f"Добавлен: {name} → {division_id}")
                st.rerun()

st.divider()
st.subheader("Список участников")

participants = [p for p in db.get("participants", []) if not p.get("deleted", False)]

if not participants:
    st.info("Пока участников нет.")
else:
    header = st.columns([0.7, 2.8, 0.8, 0.9, 1.4, 1.6, 1.4, 1.4, 0.9, 0.8, 0.8])
    header[0].markdown("**ID**")
    header[1].markdown("**ФИО**")
    header[2].markdown("**Пол**")
    header[3].markdown("**Возраст**")
    header[4].markdown("**DIV**")
    header[5].markdown("**Клуб**")
    header[6].markdown("**Регион**")
    header[7].markdown("**Город**")
    header[8].markdown("**Флаг**")
    header[9].markdown("**Edit**")
    header[10].markdown("**Del**")

    for p in participants:
        cols = st.columns([0.7, 2.8, 0.8, 0.9, 1.4, 1.6, 1.4, 1.4, 0.9, 0.8, 0.8])
        cols[0].write(p.get("id", ""))
        cols[1].write(p.get("full_name", ""))
        cols[2].write(p.get("sex", ""))
        cols[3].write(p.get("age", ""))
        cols[4].write(p.get("division_id", ""))
        cols[5].write(p.get("club", ""))
        cols[6].write(p.get("region", ""))
        cols[7].write(p.get("city", ""))

        fp = p.get("flag_path")
        if fp:
            try:
                cols[8].image(fp, width=36)
            except Exception:
                cols[8].write("⚠️")

        if cols[9].button("✏️", key=f"edit_{p['id']}"):
            st.session_state.pending_edit_id = int(p["id"])
            st.session_state.pending_delete_id = None

        if cols[10].button("❌", key=f"del_{p['id']}"):
            st.session_state.pending_delete_id = int(p["id"])
            st.session_state.pending_edit_id = None

    if st.session_state.pending_edit_id is not None:
        pid = int(st.session_state.pending_edit_id)
        target = next((x for x in participants if int(x["id"]) == pid), None)

        if target is None:
            st.session_state.pending_edit_id = None
        else:
            st.divider()
            st.subheader(f"Редактирование участника ID {pid}")

            with st.form(f"edit_participant_{pid}"):
                e1, e2, e3 = st.columns(3)
                edit_name = e1.text_input("Фамилия Имя", value=target.get("full_name", ""))
                sex_index = 0 if target.get("sex", "M") == "M" else 1
                edit_sex = e2.selectbox("Пол", ["M", "F"], index=sex_index)
                edit_age = e3.number_input(
                    "Возраст",
                    min_value=1,
                    max_value=120,
                    step=1,
                    value=int(target.get("age", 25) or 25),
                )

                e4, e5, e6 = st.columns(3)
                cat_index = 0 if target.get("category", "BEGSCAL") == "BEGSCAL" else 1
                edit_category = e4.selectbox("Категория", ["BEGSCAL", "INT"], index=cat_index)
                edit_city = e5.text_input("Город", value=target.get("city", ""))
                edit_club = e6.text_input("Клуб", value=target.get("club", ""))

                edit_region = st.text_input("Регион", value=target.get("region", ""))
                current_flag = target.get("flag_path")
                if current_flag:
                    st.caption("Текущий флаг")
                    st.image(current_flag, width=80)

                edit_flag_file = st.file_uploader(
                    "Новый флаг (если нужно заменить). Максимум 1 MB",
                    type=["png", "jpg", "jpeg"],
                    key=f"edit_flag_{pid}",
                )
                remove_flag = st.checkbox("Удалить текущий флаг", value=False, key=f"remove_flag_{pid}")

                b1, b2 = st.columns(2)
                save_edit = b1.form_submit_button("💾 Сохранить изменения")
                cancel_edit = b2.form_submit_button("Отмена")

            if cancel_edit:
                st.session_state.pending_edit_id = None
                st.rerun()

            if save_edit:
                new_name = (edit_name or "").strip()
                if not new_name:
                    st.error("ФИО пустое.")
                else:
                    new_division_id = resolve_division_id(edit_sex, edit_category)
                    old_division_id = target.get("division_id")
                    limit = int(db["settings"]["division_limits"].get(new_division_id, 0))
                    current = count_participants_in_division(db, new_division_id)
                    occupied_without_self = current - (1 if old_division_id == new_division_id else 0)

                    if limit > 0 and occupied_without_self >= limit:
                        st.error(
                            f"Лимит для {new_division_id} = {limit}. Сейчас уже {occupied_without_self}. "
                            "Перенос в этот дивизион запрещён."
                        )
                    else:
                        try:
                            new_flag_path = target.get("flag_path")
                            if remove_flag:
                                old_path = target.get("flag_path")
                                if old_path and os.path.exists(old_path):
                                    try:
                                        os.remove(old_path)
                                    except OSError:
                                        pass
                                new_flag_path = None

                            if edit_flag_file is not None:
                                new_flag_path = save_flag_image(edit_flag_file, pid)
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            for participant in db.get("participants", []):
                                if int(participant.get("id", 0)) == pid:
                                    participant["full_name"] = new_name
                                    participant["sex"] = edit_sex
                                    participant["age"] = int(edit_age)
                                    participant["category"] = edit_category
                                    participant["division_id"] = new_division_id
                                    participant["city"] = (edit_city or "").strip()
                                    participant["club"] = (edit_club or "").strip()
                                    participant["region"] = (edit_region or "").strip()
                                    participant["flag_path"] = new_flag_path
                                    break

                            save_db(db)
                            st.session_state.pending_edit_id = None
                            st.success("Карточка участника обновлена.")
                            st.rerun()

    if st.session_state.pending_delete_id is not None:
        pid = int(st.session_state.pending_delete_id)
        target = next((x for x in participants if int(x["id"]) == pid), None)
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
