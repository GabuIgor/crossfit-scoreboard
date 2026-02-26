import subprocess
from datetime import datetime

from publish.build_public import build_all


def run(cmd):
    subprocess.check_call(cmd, shell=True)


def main():
    # 1) собираем public/results.json и public/flags
    build_all()

    # 2) git add только public/*
    run("git add public/results.json public/flags public/index.html public/mobile.html")

    # 3) commit (если нечего коммитить — git вернет ошибку, обработаем простым способом)
    msg = f'Publish results {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    try:
        run(f'git commit -m "{msg}"')
    except subprocess.CalledProcessError:
        print("Nothing to commit (no changes).")

    # 4) push
    run("git push")

    print("OK: pushed to GitHub")


if __name__ == "__main__":
    main()