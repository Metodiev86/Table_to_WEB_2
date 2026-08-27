# report_template.py
import csv
import json
from datetime import datetime
from tkinter.simpledialog import askstring
import tkinter.messagebox as messagebox
from winotify import Notification

from loader import FileProcessor
from generator import HTMLGenerator
from sqlite_injector import SQLiteInjector
from DataFrame_Handler import DataTransformer
from Config import *

# --- Инициализация на обработчици ---
processor = FileProcessor()
transformer = DataTransformer()
generator = HTMLGenerator(str(TEMPLATE_FILE_PATH))



def save_metadata(report_name, category):
    metadata_file = METADATA_DIR / (report_name + ".json")
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump({"category": category}, f, ensure_ascii=False, indent=4)

def log_success(file_in=None, file_out=None):
    with open(SUCCESS_LOG, mode="a", newline="", encoding="ANSI") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([datetime.now().isoformat(), str(file_in), str(file_out)])


def log_error(file_in=None, error_msg=None):
    with open(ERROR_LOG, mode="a", newline="", encoding="ANSI") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([datetime.now().isoformat(), str(file_in), error_msg])

def toast_message_end(message):
    toast = Notification(app_id="My Report Generator",
                     title="Готово",
                     msg=f"Файлът {message} е създаден",
                     duration="short")
    toast.show()

def ask_category() -> str:
    while True:
        category = askstring(
            "Категория",
            "Моля въведете категория за отчета (напр. Справки, Разплащания, Транспорт):"
        )

        # 1. Ако потребителят е натиснал Cancel (category е None)
        if category is None:
            return ""  # Или може да вдигнете грешка: raise ValueError("Прекратено от потребителя")

        # 2. Махаме излишни интервали в началото и края
        category = category.strip()

        # 3. Проверка за празен вход
        if category:
            return category

        # Ако е празно, показваме предупреждение и цикълът се повтаря
        messagebox.showwarning("Внимание", "Полето не може да бъде празно!")

def generate_report(file_in: Path, file_out: Path, connection_string: str = None, category: str = None):
    """
    Основна функция за генериране на отчет.
    Поддържа статичен и динамичен flow според броя редове.
    """
    # Прилагаме логиката от предишния отговор:
    # ask_category се вика само ако тук category е None
    if category is None:
        category = ask_category()

    # Ако все пак category е празен низ (от Cancel), може да спрем процеса
    if not category:
        messagebox.showerror(title="Грешка", message="Генерирането е отменено.")
        return
    try:
        # 1. Зареждане на файла
        df = processor.load_file(str(file_in))

        # 2. Трансформация
        df = transformer.clean_data(df)

        # 3. Избор на flow
        row_count = len(df)
        report_name = file_out.stem

        # Записваме метаданните (категорията)
        save_metadata(report_name, category)

        if row_count < 10000:
            # Статичен отчет
            generator.generate_static_report(str(file_in), df, str(file_out))
        else:
            # Динамичен отчет (голям обем)
            db_path = DB_DIR / (report_name + ".sqlite")
            injector = SQLiteInjector(str(db_path))
            injector.inject_data(df, report_name)

            # Генериране на динамичен HTML
            generator.generate_dynamic_template(str(file_in), df, str(file_out), report_name)

        # Логване на успешен отчет
        log_success(file_in, file_out)
        toast_message_end(file_out)
        return file_out

    except Exception as e:
        # Логване на грешки
        log_error(file_in, str(e))
        return None


# --- Пример за дефиниране на фиксирани задачи ---
if __name__ == "__main__":
    # Тук може да се дефинират файлове за конкретни отчети
    input_output_files = [
        (Path(r"data\sales_january.xlsx"), OUTPUT_DIR_Public / "sales_january.html"),
        (Path(r"data\inventory.xlsx"), OUTPUT_DIR_Private / "inventory.html"),
    ]

    for file_in, file_out in input_output_files:
        generate_report(file_in, file_out)