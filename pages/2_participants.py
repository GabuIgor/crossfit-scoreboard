import hashlib
from datetime import date
from io import BytesIO

import streamlit as st
from PIL import Image

from storage import load_db, save_db, next_participant_id, count_participants_in_division, delete_participant
from config import DATA_FLAGS_DIR, MAX_FLAG_UPLOAD_BYTES, MAX_FLAG_DIMENSION
from utils import compact_page_style, parse_birth_date, birth_date_to_storage, display_birth_date

st.set_page_config(page_title="Участники", layout="wide")
compact_page_style()
st.title("👥 Участники")

db = load_db()
settings = db["settings"]
clubs = settings.get("clubs", [])

SEX_OPTIONS = {"МУЖЧИНЫ": "M", "ЖЕНЩИНЫ": "F"}
CATEGORY_OPTIONS = {"Beginners/Scaled": "BEGSCAL", "Intermediate": "INT"}
SORT_OPTIONS = {
    "ФИО": lambda p: (str(p.get("full_name") or "").lower(), int(p.get("id") or 0)),
    "Дата рождения": lambda p: (str(p.get("birth_date") or "9999-99-99"), str(p.get("full_name") or "").lower()),
    "Пол": lambda p: (str(p.get("sex") or ""), str(p.get("full_name") or "").lower()),
    "Категория": lambda p: (str(p.get("category") or ""), str(p.get("full_name") or "").lower()),
    "Дивизион": lambda p: (str(p.get("division_id") or ""), str(p.get("full_name") or "").lower()),
    "Клуб": lambda p: (str(p.get("club") or "").lower(), str(p.get("full_name") or "").lower()),
    "Регион": lambda p: (str(p.get("region") or p.get("city") or "").lower(), str(p.get("full_name") or "").lower()),
    "ID": lambda p: int(p.get("id") or 0),
}


def normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


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


def normalize_club_choice(choice: str) -> str:
    return "" if choice == "—" else choice


def club_select_options():
    return ["—"] + clubs


def duplicate_name_exists(items, full_name: str, ignore_id: int | None = None) -> bool:
    needle = (full_name or "").strip().casefold()
    if not needle:
        return False
    for item in items:
        if item.get("deleted", False):
            continue
        if ignore_id is not None and int(item.get("id", 0)) == int(ignore_id):
            continue
        if str(item.get("full_name") or "").strip().casefold() == needle:
            return True
    return False


def duplicate_warning_text(participants, full_name: str, exclude_id=None) -> str | None:
    target = normalize_name(full_name)
    if not target:
        return None
    matches = []
    for p in participants:
        if p.get("deleted", False):
            continue
        if exclude_id is not None and int(p.get("id")) == int(exclude_id):
            continue
        if normalize_name(p.get("full_name", "")) == target:
            matches.append(p)
    if not matches:
        return None
    ids = ", ".join(str(int(p.get("id"))) for p in matches)
    return f"Внимание: участник с таким ФИО уже существует (ID: {ids}). Сохранение разрешено."


def sex_to_ru(value: str) -> str:
    return "МУЖЧИНЫ" if value == "M" else "ЖЕНЩИНЫ"


def category_to_ru(value: str) -> str:
    return "Beginners/Scaled" if value == "BEGSCAL" else "Intermediate"


st.subheader("Добавить участника")
with st.form("add_participant"):
    c1, c2, c3 = st.columns(3)
    with c1:
        full_name = st.text_input("Фамилия Имя")
        sex_label = st.selectbox("Пол", list(SEX_OPTIONS.keys()))
        birth_date = st.date_input(
            "Дата рождения",
            format="DD.MM.YYYY",
            value=date(2000, 1, 1),
            min_value=date(1950, 1, 1),
            max_value=date.today(),
        )
    with c2:
        category_label = st.selectbox("Категория", list(CATEGORY_OPTIONS.keys()))
        region = st.text_input("Регион / город")
    with c3:
        club_choice = st.selectbox("Клуб", club_select_options())
        flag_file = st.file_uploader(
            f"Флаг (PNG/JPG, до {MAX_FLAG_UPLOAD_BYTES // 1024 // 1024} MB)",
            type=["png", "jpg", "jpeg"],
        )

    submitted = st.form_submit_button("➕ Добавить")

if submitted:
    participants_all = db.get("participants", [])
    name = (full_name or "").strip()
    sex = SEX_OPTIONS[sex_label]
    category = CATEGORY_OPTIONS[category_label]
    if not name:
        st.error("ФИО пустое.")
    elif not birth_date_to_storage(birth_date):
        st.error("Укажи дату рождения.")
    else:
        division_id = resolve_division_id(sex, category)
        limit = int(db["settings"]["division_limits"].get(division_id, 0))
        current = count_participants_in_division(db, division_id)

        if limit > 0 and current >= limit:
            st.error(f"Лимит для {division_id} = {limit}. Сейчас уже {current}. Добавление запрещено.")
        else:
            warning = duplicate_warning_text(participants_all, name)
            if warning:
                st.warning(warning)
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
                "birth_date": birth_date_to_storage(birth_date),
                "age": 0,
                "category": category,
                "division_id": division_id,
                "region": (region or "").strip(),
                "city": "",
                "club": normalize_club_choice(club_choice),
                "flag_path": flag_path,
                "deleted": False,
            })

            save_db(db)
            st.success(f"Участник добавлен: {name} → {division_id}")
            st.rerun()

st.divider()

participants = [p for p in db.get("participants", []) if not p.get("deleted", False)]

sort_col1, sort_col2 = st.columns([2, 1])
with sort_col1:
    sort_label = st.selectbox("Сортировать по", list(SORT_OPTIONS.keys()), index=0)
with sort_col2:
    sort_desc = st.checkbox("По убыванию", value=False)
participants.sort(key=SORT_OPTIONS[sort_label], reverse=sort_desc)

st.session_state.setdefault("pending_delete_id", None)
st.session_state.setdefault("edit_participant_id", None)

edit_id = st.session_state.edit_participant_id
if edit_id is not None:
    target = next((x for x in participants if int(x["id"]) == int(edit_id)), None)
    if target:
        st.subheader(f"Редактировать участника #{edit_id}")
        st.info(f"Сейчас редактируется: {target.get('full_name', '')}")
        with st.form(f"edit_participant_{edit_id}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                edit_name = st.text_input("Фамилия Имя", value=target.get("full_name", ""))
                current_sex_label = "МУЖЧИНЫ" if target.get("sex", "M") == "M" else "ЖЕНЩИНЫ"
                edit_sex_label = st.selectbox("Пол", list(SEX_OPTIONS.keys()), index=list(SEX_OPTIONS.keys()).index(current_sex_label))
                edit_birth_date = st.date_input(
                    "Дата рождения",
                    format="DD.MM.YYYY",
                    value=parse_birth_date(target.get("birth_date")) or date(2000, 1, 1),
                    min_value=date(1950, 1, 1),
                    max_value=date.today(),
                    key=f"edit_birth_date_{edit_id}",
                )
            with c2:
                current_cat_label = "Beginners/Scaled" if target.get("category", "BEGSCAL") == "BEGSCAL" else "Intermediate"
                edit_category_label = st.selectbox("Категория", list(CATEGORY_OPTIONS.keys()), index=list(CATEGORY_OPTIONS.keys()).index(current_cat_label))
                edit_region = st.text_input("Регион / город", value=target.get("region", "") or target.get("city", ""))
            with c3:
                club_options = club_select_options()
                current_club = target.get("club", "") or "—"
                if current_club not in club_options:
                    club_options = club_options + [current_club]
                edit_club = st.selectbox("Клуб", club_options, index=club_options.index(current_club))
                edit_flag_file = st.file_uploader(
                    "Новый флаг (необязательно)",
                    type=["png", "jpg", "jpeg"],
                    key=f"edit_flag_{edit_id}",
                )

            s1, s2 = st.columns(2)
            save_pressed = s1.form_submit_button("💾 Сохранить")
            cancel_pressed = s2.form_submit_button("Отмена")

        if cancel_pressed:
            st.session_state.edit_participant_id = None
            st.rerun()

        if save_pressed:
            edit_sex = SEX_OPTIONS[edit_sex_label]
            edit_category = CATEGORY_OPTIONS[edit_category_label]
            new_division_id = resolve_division_id(edit_sex, edit_category)
            old_division_id = str(target.get("division_id") or "")
            if new_division_id != old_division_id:
                limit = int(db["settings"]["division_limits"].get(new_division_id, 0))
                current = count_participants_in_division(db, new_division_id)
                if limit > 0 and current >= limit:
                    st.error(f"Лимит для {new_division_id} = {limit}. Сейчас уже {current}. Перенос запрещён.")
                    st.stop()

            if not birth_date_to_storage(edit_birth_date):
                st.error("Укажи дату рождения.")
                st.stop()

            warning = duplicate_warning_text(db.get("participants", []), edit_name, exclude_id=edit_id)
            if warning:
                st.warning(warning)

            duplicate_name = duplicate_name_exists(db.get("participants", []), (edit_name or "").strip(), ignore_id=int(target["id"]))
            target["full_name"] = (edit_name or "").strip()
            target["sex"] = edit_sex
            target["birth_date"] = birth_date_to_storage(edit_birth_date)
            target["age"] = 0
            target["category"] = edit_category
            target["division_id"] = new_division_id
            target["region"] = (edit_region or "").strip()
            target["city"] = ""
            target["club"] = normalize_club_choice(edit_club)
            if edit_flag_file is not None:
                try:
                    target["flag_path"] = save_flag_image(edit_flag_file, int(target["id"]))
                except ValueError as exc:
                    st.error(str(exc))
                    st.stop()

            save_db(db)
            st.session_state.edit_participant_id = None
            if duplicate_name:
                st.warning(f"Внимание: участник с таким ФИО уже есть — {target['full_name']}")
            st.success("Участник обновлён.")
            st.rerun()

        st.divider()

st.subheader("Список участников")
if not participants:
    st.info("Пока участников нет.")
else:
    header = st.columns([0.6, 0.7, 2.6, 1.0, 1.3, 1.1, 1.4, 1.5, 0.8, 0.8])
    labels = ["ID", "Edit", "ФИО", "Пол", "Дата рожд.", "DIV", "Регион", "Клуб", "Флаг", "Del"]
    for col, label in zip(header, labels):
        col.markdown(f"**{label}**")

    for p in participants:
        cols = st.columns([0.6, 0.7, 2.6, 1.0, 1.3, 1.1, 1.4, 1.5, 0.8, 0.8])
        cols[0].write(int(p["id"]))
        if cols[1].button("✏️", key=f"edit_{p['id']}"):
            st.session_state.edit_participant_id = int(p["id"])
            st.rerun()
        cols[2].write(p.get("full_name", ""))
        cols[3].write(sex_to_ru(p.get("sex", "M")))
        cols[4].write(display_birth_date(p.get("birth_date")))
        cols[5].write(p.get("division_id", ""))
        cols[6].write(p.get("region", "") or p.get("city", ""))
        cols[7].write(p.get("club", ""))
        cols[8].write("✅" if p.get("flag_path") else "—")
        if cols[9].button("🗑️", key=f"del_{p['id']}"):
            st.session_state.pending_delete_id = int(p["id"])
            st.rerun()

    pending_delete_id = st.session_state.pending_delete_id
    if pending_delete_id is not None:
        st.warning(f"Удалить участника ID {pending_delete_id}? Это скроет его из таблиц.")
        dc1, dc2 = st.columns(2)
        if dc1.button("✅ Да, удалить", key="confirm_delete"):
            delete_participant(db, int(pending_delete_id))
            save_db(db)
            st.session_state.pending_delete_id = None
            st.success("Участник удалён.")
            st.rerun()
        if dc2.button("❌ Отмена", key="cancel_delete"):
            st.session_state.pending_delete_id = None
            st.rerun()
