# main.py
import sys
from pathlib import Path
from tkinter.filedialog import asksaveasfilename
from tkinter import messagebox
from loader import DataLoader, FileProcessor
from generator import HTMLGenerator
from sqlite_injector import SQLiteInjector
from DataFrame_Handler import DataTransformer
from Load_from_External_File import Load_From_External_File


TEMPLATE_FILE = r"Template\template_Table_to_HTML.html"
OUTPUT_DIR = Path("output")
DB_DIR = Path("databases")
OUTPUT_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)

load_external_file = Load_From_External_File()
processor = FileProcessor()
transformer = DataTransformer()
generator = HTMLGenerator(TEMPLATE_FILE)

def generate_report(file_path):
    try:
        # 1. Load
        df = processor.load_file(file_path)
        
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
            
        return output_file

    except Exception as e:
        messagebox.showerror("Грешка", f"Възникна проблем: {str(e)}")
        return None

def main():
    file_path = load_external_file.select_file()

    if not file_path:
        return

    output_file = generate_report(file_path)

    if output_file:
        messagebox.showinfo(
            "Готово",
            f"Отчетът е генериран успешно:\n{output_file} \n\nМожете да го отворите с браузър."
        )

if __name__ == "__main__":
    main()



