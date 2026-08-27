import time
import os
import subprocess
import json
import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw

from loader import FileProcessor
from generator import HTMLGenerator
from sqlite_injector import SQLiteInjector
from DataFrame_Handler import DataTransformer

CREATE_NO_WINDOW = 0x08000000
TEMPLATE_FILE = r"Template\template_Table_to_HTML.html"
OUTPUT_DIR = Path("output")
DB_DIR = Path("databases")
OUTPUT_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)

# 🔹 Конфигурация: файл → скрипт
WATCH_CONFIG = {
    r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\Задължения Доставчици\Текущи задължения към Доставчици.xlsx": "Zadalzhenia_Dostavchitsi",
    r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\Задължения Доставчици\РИЛА Текущи задължения към Доставчици.xlsx": "Rila_Zadalzhenia",
    r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\ТРАНСПОРТ ОБЩО\2026\Международен Транспорт.xlsx": "Transport_Obshto",
}

class SystemWatcher(FileSystemEventHandler):
    def __init__(self):
        self.last_run = {}
        self.processor = FileProcessor()
        self.transformer = DataTransformer()
        self.generator = HTMLGenerator(TEMPLATE_FILE)

    def on_modified(self, event):
        if event.is_directory:
            return

        changed_file = os.path.abspath(event.src_path)
        for watched_file, report_name in WATCH_CONFIG.items():
            if changed_file.lower() == watched_file.lower():
                now = time.time()
                last_time = self.last_run.get(watched_file, 0)
                if now - last_time < 5:  # 5s debounce
                    return
                self.last_run[watched_file] = now
                self.process_change(watched_file, report_name)

    def process_change(self, file_path, report_name):
        print(f"🔄 Промяна засечена: {file_path}")
        try:
            # 1. Load
            df = self.processor.load_file(file_path)
            # 2. Transform
            df = self.transformer.clean_data(df)
            
            # 3. Decide Flow (Static or Dynamic)
            row_count = len(df)
            output_html = OUTPUT_DIR / f"{report_name}.html"
            
            if row_count < 10000:
                # Static flow
                self.generator.generate_static_report(file_path, df, str(output_html))
                print(f"✅ Статичен отчет генериран: {output_html}")
            else:
                # Dynamic flow (Heavy Data)
                db_path = DB_DIR / f"{report_name}.sqlite"
                injector = SQLiteInjector(str(db_path))
                injector.inject_data(df, report_name)
                
                # Generate dynamic template
                self.generator.generate_dynamic_template(file_path, df, str(output_html))
                print(f"✅ Динамичен отчет генериран: {output_html} (База: {db_path})")
                
        except Exception as e:
            print(f"❌ Грешка при обработка: {e}")

    def run_daily_update(self):
        # Стартира веригата за тежки данни веднъж дневно
        print("📅 Изпълнение на дневен ъпдейт...")
        for file_path, report_name in WATCH_CONFIG.items():
            if os.path.exists(file_path):
                self.process_change(file_path, report_name)

def create_tray_image():
    image = Image.new('RGB', (64, 64), color='green')
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill='white')
    return image

def main():
    observer = Observer()
    handler = SystemWatcher()
    
    # Извличаме директориите (уникални)
    watch_dirs = list(set(os.path.dirname(path) for path in WATCH_CONFIG.keys()))
    for directory in watch_dirs:
        if os.path.exists(directory):
            observer.schedule(handler, path=directory, recursive=False)

    observer.start()

    def on_exit(icon, item):
        observer.stop()
        icon.stop()

    icon = Icon(
        "Watcher",
        create_tray_image(),
        "Системен Монитор (Table to WEB)",
        menu=Menu(MenuItem("Изход", on_exit))
    )

    print("🚀 Системата за мониторинг е стартирана.")
    icon.run()
    observer.join()

if __name__ == "__main__":
    main()