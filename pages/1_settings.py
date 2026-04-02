from io import BytesIO

import streamlit as st
from PIL import Image

from storage import load_db, save_db, default_display_settings, clear_results, clear_all_data, default_team_scoring, default_workouts, WORKOUT_TYPES
from config import DIVISIONS, DATA_FLAGS_DIR, MAX_FLAG_DIMENSION, MAX_FLAG_UPLOAD_BYTES
from utils import compact_page_style

st.set_page_config(page_title="Settings", layout="wide")
compact_page_style()
st.title("⚙️ Настройки")

db = load_db()
settings = db["settings"]

if "confirm_clear_results" not in st.session_state:
    st.session_state.confirm_clear_results = False
if "confirm_clear_all" not in st.session_state:
    st.session_state.confirm_clear_all = False

settings.setdefault("display", default_display_settings())
settings.setdefault("clubs", [])
settings.setdefault("club_profiles", {})
settings.setdefault("team_scoring", default_team_scoring())
settings.setdefault("workouts", default_workouts())


def save_club_flag_image(flag_file, club_name: str) -> str:
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
    safe_name = "club_" + "".join(ch.lower() if ch.isalnum() else "_" for ch in club_name)[:80]
    out_path = DATA_FLAGS_DIR / f"{safe_name}.png"
    img.save(out_path, format="PNG", optimize=True)
    return str(out_path.as_posix())


st.subheader("Лимиты участников по дивизионам")
limits = settings["division_limits"]
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
st.subheader("Клубы")
club_list = settings.setdefault("clubs", [])
club_profiles = settings.setdefault("club_profiles", {})
club_text = st.text_area(
    "Список клубов",
    value="\n".join(club_list),
    height=160,
    help="По одному клубу в строке. Эти клубы будут доступны в выпадающем списке при добавлении и редактировании атлета.",
)
parsed_clubs = []
seen = set()
for line in club_text.splitlines():
    name = line.strip()
    if not name:
        continue
    key = name.casefold()
    if key in seen:
        continue
    seen.add(key)
    parsed_clubs.append(name)
parsed_clubs.sort(key=lambda x: x.casefold())
if parsed_clubs != club_list:
    settings["clubs"] = parsed_clubs
    club_list = parsed_clubs
    changed = True
for club_name in club_list:
    club_profiles.setdefault(club_name, {"city": "", "flag_path": ""})
for key in list(club_profiles.keys()):
    if key not in club_list:
        club_profiles.pop(key, None)
        changed = True

st.caption("Ниже можно настроить уже введённые клубы: указать город и загрузить флаг.")
for club_name in club_list:
    with st.container(border=True):
        st.markdown(f"**{club_name}**")
        profile = club_profiles.setdefault(club_name, {"city": "", "flag_path": ""})
        cc1, cc2 = st.columns([2, 2])
        new_city = cc1.text_input("Город", value=profile.get("city", ""), key=f"club_city_{club_name}")
        if new_city != profile.get("city", ""):
            profile["city"] = new_city.strip()
            changed = True
        uploaded = cc2.file_uploader("Флаг клуба", type=["png", "jpg", "jpeg"], key=f"club_flag_{club_name}")
        if uploaded is not None:
            try:
                new_flag_path = save_club_flag_image(uploaded, club_name)
                if new_flag_path != profile.get("flag_path", ""):
                    profile["flag_path"] = new_flag_path
                    changed = True
                    st.success(f"Флаг клуба «{club_name}» обновлён.")
            except ValueError as exc:
                st.error(str(exc))
        if profile.get("flag_path"):
            st.caption(f"Флаг загружен: {profile.get('flag_path')}")

st.divider()
st.subheader("Клубный зачёт")
team_scoring = settings.setdefault("team_scoring", default_team_scoring())
priority_score_id = str(team_scoring.get("priority_score_id") or "WOD3")
score_ids = [s["id"] for s in settings.get("scores", [])]
if priority_score_id not in score_ids and score_ids:
    priority_score_id = score_ids[-1]
    team_scoring["priority_score_id"] = priority_score_id
    changed = True

new_priority = st.selectbox("Приоритетный комплекс", score_ids, index=score_ids.index(priority_score_id) if priority_score_id in score_ids else 0)
if new_priority != priority_score_id:
    team_scoring["priority_score_id"] = new_priority
    changed = True

places_cfg = team_scoring.setdefault("places", [1, 2, 3])
place_cols = st.columns(3)
for idx, place in enumerate((1, 2, 3)):
    with place_cols[idx]:
        checked = place in places_cfg
        new_checked = st.checkbox(f"Начислять за {place} место", value=checked, key=f"team_place_{place}")
        if new_checked and place not in places_cfg:
            places_cfg.append(place)
            places_cfg.sort()
            changed = True
        if not new_checked and place in places_cfg:
            places_cfg.remove(place)
            changed = True

st.caption("Ниже задаются очки клубного зачёта за призовые места в каждой индивидуальной категории.")
for div in DIVISIONS:
    div_id = div["id"]
    cur_map = team_scoring.setdefault("division_points", {}).setdefault(div_id, {"1": 0, "2": 0, "3": 0})
    st.markdown(f"**{div['title']}**")
    cols = st.columns(3)
    for idx, place in enumerate((1, 2, 3)):
        cur_val = int(cur_map.get(str(place), 0))
        with cols[idx]:
            new_val = st.number_input(f"{place} место", min_value=0, step=1, value=cur_val, key=f"team_pts_{div_id}_{place}")
        if int(new_val) != cur_val:
            cur_map[str(place)] = int(new_val)
            changed = True

st.divider()
st.subheader("Настройка зачётов")
score_rows = settings["scores"]
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
        new_cap = st.checkbox(
            "Разрешить Time cap (только для time)",
            value=bool(s.get("time_cap_enabled", False)),
            key=f"cap_{s['id']}",
        )
        if new_cap != bool(s.get("time_cap_enabled", False)):
            s["time_cap_enabled"] = bool(new_cap)
            changed = True

st.divider()
st.subheader("Комплексы")
workouts = settings.setdefault("workouts", default_workouts())
structure = workouts.setdefault("structure", default_workouts()["structure"])
entries = workouts.setdefault("entries", default_workouts()["entries"])
count_default = len(structure)
new_count = st.number_input("Количество WOD", min_value=1, max_value=10, step=1, value=count_default)
if int(new_count) != count_default:
    new_structure = []
    for idx in range(1, int(new_count) + 1):
        base = f"WOD{idx}"
        existing = next((x for x in structure if str(x.get("base")) == base), None)
        new_structure.append({"base": base, "parts": int(existing.get("parts", 1)) if existing else 1})
    workouts["structure"] = new_structure
    structure = new_structure
    changed = True

for item in structure:
    base = item["base"]
    current_parts = int(item.get("parts", 1))
    new_parts = st.number_input(f"{base}: количество частей", min_value=1, max_value=4, step=1, value=current_parts, key=f"parts_{base}")
    if int(new_parts) != current_parts:
        item["parts"] = int(new_parts)
        changed = True

# refresh entries keys based on structure
workout_ids = []
for item in structure:
    base = item["base"]
    parts = int(item.get("parts", 1))
    if parts <= 1:
        workout_ids.append(base)
    else:
        workout_ids.extend([f"{base}{chr(64 + idx)}" for idx in range(1, parts + 1)])
for div in DIVISIONS:
    div_entries = entries.setdefault(div["id"], {})
    for wid in workout_ids:
        div_entries.setdefault(wid, {"label": wid, "type": "", "time_cap": "", "description": ""})
    for key in list(div_entries.keys()):
        if key not in workout_ids:
            div_entries.pop(key, None)
            changed = True

for div in DIVISIONS:
    st.markdown(f"### {div['title']}")
    div_entries = entries.setdefault(div["id"], {})
    for wid in workout_ids:
        with st.container(border=True):
            st.markdown(f"**{wid}**")
            e = div_entries.setdefault(wid, {"label": wid, "type": "", "time_cap": "", "description": ""})
            c1, c2 = st.columns(2)
            new_label = c1.text_input("Обозначение", value=e.get("label", wid), key=f"workout_label_{div['id']}_{wid}")
            new_type = c2.selectbox("Тип комплекса", [""] + WORKOUT_TYPES, index=([""] + WORKOUT_TYPES).index(e.get("type", "") if e.get("type", "") in ([""] + WORKOUT_TYPES) else ""), key=f"workout_type_{div['id']}_{wid}")
            new_cap = st.text_input("Лимит времени", value=e.get("time_cap", ""), key=f"workout_cap_{div['id']}_{wid}", placeholder="например 10 мин")
            new_desc = st.text_area("Описание", value=e.get("description", ""), key=f"workout_desc_{div['id']}_{wid}", height=100)
            if new_label != e.get("label", wid):
                e["label"] = new_label.strip() or wid
                changed = True
            if new_type != e.get("type", ""):
                e["type"] = new_type
                changed = True
            if new_cap != e.get("time_cap", ""):
                e["time_cap"] = new_cap.strip()
                changed = True
            if new_desc != e.get("description", ""):
                e["description"] = new_desc.strip()
                changed = True

st.divider()
st.subheader("Ручная настройка отображения экранов")
st.caption("Эти настройки попадают в public-экраны после Publish.")

display = settings["display"]
display_labels = {
    "section_title_size": "Размер заголовков разделов",
    "card_title_size": "Размер заголовков блоков",
    "table_text_size": "Размер текста таблиц",
    "meta_text_size": "Размер вторичного текста",
    "row_height": "Вертикальный отступ строк",
    "block_gap": "Отступы между блоками",
    "container_scale": "Масштаб контейнеров",
}
display_ranges = {
    "section_title_size": (10, 52, 1),
    "card_title_size": (10, 44, 1),
    "table_text_size": (7, 30, 1),
    "meta_text_size": (6, 24, 1),
    "row_height": (1, 20, 1),
    "block_gap": (2, 36, 1),
    "container_scale": (0.6, 1.6, 0.01),
}

main_display = display.setdefault("main", default_display_settings()["main"])
scene_duration = int(main_display.get("scene_duration_sec", 10))
new_scene_duration = st.slider("Время смены экранов ТВ (сек)", min_value=3, max_value=60, value=scene_duration, step=1)
if new_scene_duration != scene_duration:
    main_display["scene_duration_sec"] = int(new_scene_duration)
    changed = True

for screen_key, title in (("main", "Основные экраны"), ("mobile", "Мобильный экран")):
    st.markdown(f"### {title}")
    cols = st.columns(2)
    screen_settings = display.setdefault(screen_key, default_display_settings()[screen_key])
    for idx, (key, label) in enumerate(display_labels.items()):
        col = cols[idx % 2]
        min_v, max_v, step = display_ranges[key]
        current = screen_settings.get(key, default_display_settings()[screen_key][key])
        with col:
            if isinstance(step, float):
                new_value = st.slider(label, min_value=float(min_v), max_value=float(max_v), value=float(current), step=float(step), key=f"display_{screen_key}_{key}")
            else:
                new_value = st.slider(label, min_value=int(min_v), max_value=int(max_v), value=int(current), step=int(step), key=f"display_{screen_key}_{key}")
        if new_value != current:
            screen_settings[key] = new_value
            changed = True

    if st.button(f"Сбросить настройки: {title}", key=f"reset_display_{screen_key}"):
        display[screen_key] = default_display_settings()[screen_key].copy()
        save_db(db)
        st.success(f"Настройки '{title}' сброшены.")
        st.rerun()

st.divider()
st.subheader("Сервисные действия")
left, right = st.columns(2)
with left:
    st.warning("Очистить только результаты: атлеты, клубы и заходы останутся.")
    if not st.session_state.confirm_clear_results:
        if st.button("🧹 Очистить результаты", key="clear_results_btn"):
            st.session_state.confirm_clear_results = True
            st.rerun()
    else:
        st.error("Подтверди очистку результатов. Это действие нельзя отменить.")
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("✅ Да, очистить результаты", key="confirm_clear_results_yes"):
            clear_results(db)
            save_db(db)
            st.session_state.confirm_clear_results = False
            st.success("Результаты очищены. Атлеты, клубы и заходы сохранены.")
            st.rerun()
        if confirm_cols[1].button("❌ Отмена", key="confirm_clear_results_no"):
            st.session_state.confirm_clear_results = False
            st.rerun()
with right:
    st.error("Полное удаление данных: атлеты, результаты и заходы будут очищены.")
    if not st.session_state.confirm_clear_all:
        if st.button("🗑️ Удалить всё", key="clear_all_btn"):
            st.session_state.confirm_clear_all = True
            st.rerun()
    else:
        st.error("Подтверди полное удаление. Это действие нельзя отменить.")
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("✅ Да, удалить всё", key="confirm_clear_all_yes"):
            clear_all_data(db)
            save_db(db)
            st.session_state.confirm_clear_all = False
            st.success("Все данные очищены.")
            st.rerun()
        if confirm_cols[1].button("❌ Отмена", key="confirm_clear_all_no"):
            st.session_state.confirm_clear_all = False
            st.rerun()

st.divider()
if st.button("💾 Сохранить настройки", type="primary"):
    save_db(db)
    st.success("Настройки сохранены.")
elif changed:
    st.warning("Есть изменения. Нажми «Сохранить настройки».")
