import subprocess
import shutil
from datetime import datetime


def run(cmd):
    print("$", " ".join(cmd))
    subprocess.check_call(cmd)


def main():

    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git не найден в PATH")

    print("=== BUILD ===")
    run(["python", "-m", "publish.build_public"])

    print("\n=== GIT ADD ===")
    run([git, "add", "-A", "docs"])

    print("\n=== STAGED CHECK ===")
    try:
        subprocess.check_call([git, "diff", "--cached", "--quiet"])
        print("Нет изменений для коммита")
        return
    except subprocess.CalledProcessError:
        pass

    print("\n=== GIT STATUS ===")
    run([git, "status", "--porcelain"])

    print("\n=== GIT COMMIT ===")
    msg = f"Publish results {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    run([git, "commit", "-m", msg])

    print("\n=== REMOTE CHECK ===")
    run([git, "remote", "get-url", "origin"])

    print("\n=== GIT PULL ===")
    try:
        run([git, "pull", "--rebase", "--autostash", "origin", "main"])
    except subprocess.CalledProcessError:
        print("Pull не удался, пробуем продолжить")

    print("\n=== GIT PUSH ===")
    run([git, "push", "origin", "main"])

    print("\nПубликация завершена")


if __name__ == "__main__":
    main()