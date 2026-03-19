import streamlit as st
from storage import load_db, save_db, default_display_settings, clear_results, clear_all_data
from config import DIVISIONS
from utils import compact_page_style

st.set_page_config(page_title="Settings", layout="wide")
compact_page_style()
st.title("⚙️ Settings")

db = load_db()
settings = db["settings"]
settings.setdefault("display", default_display_settings())

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
st.subheader("Настройки TV / основных экранов")
main_display = db["settings"].setdefault("display", {}).setdefault("main", {})

def _main_slider(label: str, key: str, min_v: int, max_v: int, default: int, step: int = 1):
    global changed
    current = int(main_display.get(key, default) or default)
    new_val = st.slider(label, min_value=min_v, max_value=max_v, value=current, step=step, key=f"main_{key}")
    if int(new_val) != current:
        main_display[key] = int(new_val)
        changed = True

c1, c2 = st.columns(2)
with c1:
    _main_slider("Размер верхнего заголовка TV", "page_title_font_size", 16, 36, 22)
    _main_slider("Размер заголовков разделов TV", "section_title_font_size", 14, 32, 18)
    _main_slider("Размер заголовков карточек TV", "card_title_font_size", 12, 28, 16)
    _main_slider("Размер текста таблиц TV", "table_font_size", 9, 20, 11)
with c2:
    _main_slider("Размер имени атлета TV", "athlete_font_size", 10, 24, 13)
    _main_slider("Размер вторичного текста TV", "meta_font_size", 9, 20, 11)
    _main_slider("Размер заголовка захода TV", "heat_title_font_size", 12, 28, 16)
    _main_slider("Размер текста в заходах TV", "heat_text_font_size", 10, 22, 12)

st.divider()
st.subheader("Настройки мобильного экрана")
mobile_display = db["settings"].setdefault("display", {}).setdefault("mobile", {})

def _slider(label: str, key: str, min_v: int, max_v: int, step: int = 1):
    global changed
    current = int(mobile_display.get(key, 0) or 0)
    new_val = st.slider(label, min_value=min_v, max_value=max_v, value=current, step=step, key=f"mobile_{key}")
    if int(new_val) != current:
        mobile_display[key] = int(new_val)
        changed = True

c1, c2 = st.columns(2)
with c1:
    _slider("Размер текста таблиц (mobile)", "table_font_size", 10, 18)
    _slider("Размер вторичного текста (mobile)", "secondary_font_size", 9, 16)
    _slider("Размер заголовка захода (mobile)", "heat_title_font_size", 12, 24)
with c2:
    _slider("Размер имени атлета в заходе (mobile)", "heat_text_font_size", 11, 22)
    _slider("Размер номера дорожки (mobile)", "heat_lane_font_size", 10, 20)
    _slider("Ширина карточки захода (mobile)", "heat_card_width", 140, 260, step=10)

st.divider()
st.subheader("Ручная настройка отображения экранов")
st.caption("Эти настройки попадают в public-экраны после Publish и помогают уместить больше информации на ТВ и mobile.")

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
    "section_title_size": (14, 36, 1),
    "card_title_size": (12, 30, 1),
    "table_text_size": (9, 22, 1),
    "meta_text_size": (8, 18, 1),
    "row_height": (2, 14, 1),
    "block_gap": (4, 24, 1),
    "container_scale": (0.8, 1.2, 0.01),
}

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
    if st.button("🧹 Очистить результаты", key="clear_results_btn"):
        clear_results(db)
        save_db(db)
        st.success("Результаты очищены. Атлеты, клубы и заходы сохранены.")
        st.rerun()
with right:
    st.error("Полное удаление данных: атлеты, результаты и заходы будут очищены.")
    if st.button("🗑️ Удалить всё", key="clear_all_btn"):
        clear_all_data(db)
        save_db(db)
        st.success("Все данные очищены.")
        st.rerun()

st.divider()
if st.button("💾 Save Settings", type="primary"):
    save_db(db)
    st.success("Сохранено.")
elif changed:
    st.warning("Есть изменения. Нажми Save Settings.")
