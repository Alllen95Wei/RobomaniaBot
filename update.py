import subprocess
from time import sleep


def update(pid, os):
    get_update_files()
    sleep(5)
    restart_running_bot(pid, os)


def get_update_files():
    subprocess.run(["git", "fetch", "--all"])
    subprocess.run(['git', 'reset', '--hard', 'origin/main'])
    subprocess.run(['git', 'pull'])


def restart_running_bot(pid, os):
    subprocess.Popen("run_in_robomania.bat", creationflags=subprocess.CREATE_NEW_CONSOLE)
    kill_running_bot(pid, os)


def kill_running_bot(pid, os):
    if os == "Windows":
        subprocess.run(['taskkill', '/f', '/PID', str(format(pid))])
    elif os == "Linux":
        subprocess.run(['kill', '-9', str(format(pid))])


if __name__ == '__main__':
    get_update_files()
    print("已經嘗試取得更新檔案，請手動重啟機器人。")
    sleep(10)
