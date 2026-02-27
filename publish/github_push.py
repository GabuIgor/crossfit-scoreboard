import subprocess
from datetime import datetime
from pathlib import Path
import shutil

from publish.build_public import build_all


def find_git_exe() -> str:
    """
    Пытаемся найти git.exe:
    1) через PATH (shutil.which)
    2) через стандартные пути установки Git for Windows
    """
    git = shutil.which("git")
    if git:
        return git

    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c

    raise RuntimeError(
        "git.exe не найден. Убедись, что Git for Windows установлен, "
        "или добавь Git в PATH. (Проверь: where git)"
    )


def run(cmd_list):
    """Запускаем команду без shell=True (так надежнее на Windows)."""
    subprocess.check_call(cmd_list)


def main():
    git = find_git_exe()

    # 1) Собираем docs/results.json и docs/flags
    build_all()

    # 2) git add
    run([git, "add", "docs/results.json", "docs/flags", "docs/index.html", "docs/mobile.html"])

    # 3) commit
    msg = f"Publish results {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        run([git, "commit", "-m", msg])
    except subprocess.CalledProcessError:
        # нечего коммитить
        print("Nothing to commit (no changes).")

    # 4) push
    run([git, "push"])

    print("Publish OK")


if __name__ == "__main__":
    main()