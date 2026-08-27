"""Модел на справка с optional параметри."""
# report_template.py
import csv
from datetime import datetime
from typing import Union
import pandas as pd

from loader import FileProcessor
from generator import HTMLGenerator
from sqlite_injector import SQLiteInjector
from DataFrame_Handler import DataTransformer
from Config import *

from tkinter.simpledialog import askstring
import tkinter.messagebox as messagebox
from winotify import Notification

from report_model import Report, save_report_metadata


# --- Инициализация на обработчици ---
processor = FileProcessor()
transformer = DataTransformer()
generator = HTMLGenerator(str(TEMPLATE_FILE_PATH))

import json


def log_success(file_in=None, file_out=None, message=None):
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
            return ""

        # 2. Махаме излишни интервали в началото и края
        category = category.strip()

        # 3. Проверка за празен вход
        if category:
            return category

        # Ако е празен, показваме предупреждение и цикълът се повтаря
        messagebox.showwarning("Внимание", "Полето не може да бъде празно!")


def generate_report(file_in: Path, file_out: Path, category: str = None, conn_str: str = None, is_rebuild: bool = True, is_dinamic: bool = False):
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
        report_name = file_out.stem

        # Проверка дали справката има параметри
        report = Report.load(report_name)
        if report and report.has_parameters:
            # Справката има параметри - не изпълняваме SQL заявка, просто генерираме шаблона
            # Създаваме празен DataFrame с една фиктивна колона
            df = pd.DataFrame({"placeholder": []})
            source_name = str(file_in)

            # Записваме метаданните
            save_report_metadata(report_name, category)

            # Генерираме динамичен шаблон (защото ще се попълва през Flask)
            generator.generate_dynamic_template(str(file_in), df, str(file_out), report_name)

            # Логване на успешен отчет
            log_success(file_in, file_out)
            toast_message_end(file_out)
            return file_out

        # 1. Зареждане на файла (за справки без параметри)
        df = processor.load_file(str(file_in), connection_string=conn_str)
        source_name = str(file_in)

        # 2. Трансформация
        df = transformer.clean_data(df)

        # 3. Избор на flow
        row_count = len(df)

        # Записваме метаданните (категорията)
        save_report_metadata(report_name, category)

        def _generate_dinamic_report():
            # Динамичен отчет (голям обем)

            db_path = DB_DIR / (report_name + ".sqlite")
            injector = SQLiteInjector(str(db_path))
            print(f"[DEBUG] report_name = {report_name!r}")
            print(f"[DEBUG] db_path     = {db_path.resolve()}")
            print(f"[DEBUG] db_path.exists() = {db_path.exists()}")
            print(f"[DEBUG] is_rebuild  = {is_rebuild}")
            if is_rebuild:
                # Старо поведение: пълен rebuild
                injector.inject_data(df, report_name)
            else:
                # Ново поведение: ако базата съществува -> append; иначе първоначално създаване
                if db_path.exists():
                    try:
                        injector.append_data(df, report_name)
                    except Exception as e:
                        import traceback
                        tb = traceback.format_exc()
                        print(f"❌ ПЪЛНА ГРЕШКА при append:\n{tb}")
                        raise
                else:
                    injector.inject_data(df, report_name)

            # Генериране на динамичен HTML
            generator.generate_dynamic_template(str(file_in), df, str(file_out), report_name)

        if is_dinamic:
            _generate_dinamic_report()
        else:

            if row_count < 10000:
                # Статичен отчет
                generator.generate_static_report(str(file_in), df, str(file_out))
            else:
                _generate_dinamic_report()

        # Логване на успешен отчет
        log_success(file_in, file_out)
        toast_message_end(file_out)
        return file_out

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"ERROR: ПЪЛНА ГРЕШКА:\n{tb}")
        # Логване на грешки
        log_error(file_in, str(e))
        return None




