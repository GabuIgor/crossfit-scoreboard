import subprocess
from datetime import datetime
from pathlib import Path
import shutil

from publish.build_public import build_all


def find_git_exe():
    """Ищем git.exe"""
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

    raise RuntimeError("Git не найден. Установи Git for Windows.")


def run(cmd):
    """Запуск команды"""
    subprocess.check_call(cmd)


def main():
    git = find_git_exe()

    # 1️⃣ Собираем docs/results.json и флаги
    build_all()

    # 2️⃣ Добавляем файлы
    run([
        git,
        "add",
        "docs/results.json",
        "docs/flags",
        "docs/index.html",
        "docs/mobile.html",
    ])

    # 3️⃣ Commit
    msg = f"Publish results {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        run([git, "commit", "-m", msg])
    except subprocess.CalledProcessError:
        print("Nothing to commit (no changes).")

    # 4️⃣ Проверяем remote origin
    try:
        subprocess.check_call([git, "remote", "get-url", "origin"])
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "\n❌ Remote origin НЕ настроен.\n"
            "Выполни в PowerShell:\n\n"
            "git remote add origin https://github.com/GabuIgor/crossfit-scoreboard.git\n"
            "git push -u origin main\n"
        )

    # 5️⃣ Push
    run([git, "push"])

    print("✅ Publish OK")


if __name__ == "__main__":
    main()