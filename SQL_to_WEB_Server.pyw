# main.py
import csv
from datetime import datetime
from pathlib import Path
from tkinter.filedialog import asksaveasfilename
from tkinter import messagebox
from loader import DataLoader, FileProcessor
from generator import HTMLGenerator
from sqlite_injector import SQLiteInjector
from DataFrame_Handler import DataTransformer
from Load_from_External_File import Load_From_External_File
import db_config
from tkinter.simpledialog import askstring

TEMPLATE_FILE = r"Template\template_Table_to_HTML.html"
OUTPUT_DIR = Path("output")
DB_DIR = Path("databases")
METADATA_DIR = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\metadata")
LOG_DIR = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\logs")
OUTPUT_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)

load_external_file = Load_From_External_File()
processor = FileProcessor()
transformer = DataTransformer()
generator = HTMLGenerator(TEMPLATE_FILE)


SUCCESS_LOG = LOG_DIR / "success_log.csv"
ERROR_LOG = LOG_DIR / "error_log.csv"
import json

def save_metadata(report_name, category):
    metadata_file = METADATA_DIR / (report_name + ".json")
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump({"category": category}, f, ensure_ascii=False, indent=4)

def log_success(file_in, file_out):
    with open(SUCCESS_LOG, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([datetime.now().isoformat(), str(file_in), str(file_out)])


def log_error(file_in, error_msg):
    with open(ERROR_LOG, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([datetime.now().isoformat(), str(file_in), error_msg])

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

def generate_report(file_path, category: str = None):
    # Прилагаме логиката от предишния отговор:
    # ask_category се вика само ако тук category е None
    if category is None:
        category = ask_category()

    # Ако все пак category е празен низ (от Cancel), може да спрем процеса
    if not category:
        messagebox.showerror(title="Грешка", message="Генерирането е отменено.")
        return
    try:
        # 1. Load
        df = processor.load_file(file_path, connection_string=db_config.MSSQL_CONN_STR)
        
        # 2. Transform
        df = transformer.clean_data(df)
        
        # 3. Decide Flow
        row_count = len(df)
        
        
        output_file = asksaveasfilename(
            title="Запис на отчет", 
            defaultextension=".html", 
            filetypes=[("HTML files", "*.html")],
            initialfile=Path(file_path).stem + ".html"
        )

        if not output_file:
            return None

        report_name = Path(output_file).stem
        
        # Записваме метаданните (категорията)
        save_metadata(report_name, category)

        if row_count < 10000:
            # Static flow
            generator.generate_static_report(file_path, df, output_file)
        else:
            # Dynamic flow (Heavy Data)
            db_path = DB_DIR / (report_name + ".sqlite")
            injector = SQLiteInjector(str(db_path))
            injector.inject_data(df, report_name)
            
            # Generate dynamic template
            generator.generate_dynamic_template(file_path, df, output_file, report_name)
            # Логване на успешен отчет
            log_success(file_path, output_file)
            
        return output_file

    except Exception as e:
        messagebox.showerror("Грешка", f"Възникна проблем: {str(e)}")
        return None

def main():
    file_path = load_external_file.select_file()

    if not file_path:
        return

    output_file = generate_report(file_path, category=None)

    if output_file:
        messagebox.showinfo(
            "Готово",
            f"Отчетът е генериран успешно:\n{output_file} \n\nМожете да го отворите с браузър."
        )

if __name__ == "__main__":
    main()



