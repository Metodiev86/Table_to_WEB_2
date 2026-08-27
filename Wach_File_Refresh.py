import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import os
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw

CREATE_NO_WINDOW = 0x08000000

# 🔹 Конфигурация: файл → скрипт
WATCH_CONFIG = {
    r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\Задължения Доставчици\Текущи задължения към Доставчици.xlsx": r"D:\Stoyan\SQLScript\SatbiDi\AJUR_ЗАДЪЛЖЕНИЯ_ДОСТАВЧИЦИ\WEB\generate.py",
    r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\Задължения Доставчици\РИЛА Текущи задължения към Доставчици.xlsx" : r"D:\Stoyan\SQLScript\SatbiDi\Рила_Дълг\WEB\generate.py",
    r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\ТРАНСПОРТ ОБЩО\2026\Международен Транспорт.xlsx": r"D:\Stoyan\SQLScript\SatbiDi\TRANSPORT\to_web_transport.py",
}

# Извличаме директориите (уникални)
WATCH_DIRS = list(set(os.path.dirname(path) for path in WATCH_CONFIG.keys()))


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self):
        # debounce защита (Excel trigger-ва много събития)
        self.last_run = {}

    def on_modified(self, event):
        if event.is_directory:
            return

        changed_file = os.path.abspath(event.src_path)

        for watched_file, script in WATCH_CONFIG.items():
            if changed_file.lower() == watched_file.lower():

                now = time.time()
                last_time = self.last_run.get(watched_file, 0)

                # ⛔ debounce (примерно 2 секунди)
                if now - last_time < 2:
                    return

                self.last_run[watched_file] = now

                print(f"🔄 Промяна: {watched_file} → стартира {script}")

                subprocess.Popen(
                    ["python", script],
                    cwd=os.path.dirname(script),
                    creationflags=CREATE_NO_WINDOW
                )


# 🔹 Observer setup
observer = Observer()
event_handler = FileChangeHandler()

for directory in WATCH_DIRS:
    observer.schedule(event_handler, path=directory, recursive=False)

observer.start()


# 🔹 Tray icon
def create_image():
    image = Image.new('RGB', (64, 64), color='green')
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill='white')
    return image


def on_exit(icon, item):
    observer.stop()
    icon.stop()


icon = Icon(
    "Watcher",
    create_image(),
    "Промени в реално време",
    menu=Menu(MenuItem("Изход", on_exit))
)

icon.run()


# 🔹 Main loop
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()

observer.join()