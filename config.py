from pathlib import Path

# Папки проекта
DATA_DIR = Path("data")
PUBLIC_DIR = Path("public")
PUBLISH_DIR = Path("publish")
DOCS_DIR = Path("docs")

# Файлы
DB_FILE = DATA_DIR / "db.json"
DATA_FLAGS_DIR = DATA_DIR / "flags"
PUBLIC_RESULTS_FILE = PUBLIC_DIR / "results.json"
PUBLIC_FLAGS_DIR = PUBLIC_DIR / "flags"
DOCS_RESULTS_FILE = DOCS_DIR / "results.json"
DOCS_FLAGS_DIR = DOCS_DIR / "flags"

# Ограничения
MAX_FLAG_UPLOAD_BYTES = 1 * 1024 * 1024  # 1 MB
MAX_FLAG_DIMENSION = 512

# Дивизионы (4 таблицы)
DIVISIONS = [
    {"id": "BEGSCAL_F", "title": "Beginners/Scaled — Women", "sex": "F", "category": "BEGSCAL"},
    {"id": "BEGSCAL_M", "title": "Beginners/Scaled — Men", "sex": "M", "category": "BEGSCAL"},
    {"id": "INT_F",     "title": "Intermediate — Women",     "sex": "F", "category": "INT"},
    {"id": "INT_M",     "title": "Intermediate — Men",       "sex": "M", "category": "INT"},
]

DEFAULT_SCORES = [
    {
        "id": "WOD1",
        "title": "Комплекс 1",
        "type": "time",
        "time_cap_enabled": True,
    },
    {
        "id": "WOD2A",
        "title": "Комплекс 2 — Зачёт 1",
        "type": "reps",
        "time_cap_enabled": False,
    },
    {
        "id": "WOD2B",
        "title": "Комплекс 2 — Зачёт 2",
        "type": "weight",
        "time_cap_enabled": False,
    },
    {
        "id": "WOD3",
        "title": "Комплекс 3",
        "type": "time",
        "time_cap_enabled": True,
    },
]
