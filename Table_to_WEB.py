# main.py
import sys
from pathlib import Path
from tkinter.filedialog import asksaveasfilename
from tkinter import messagebox
from loader import DataLoader
from generator import DataTableGenerator
from Load_from_External_File import Load_From_External_File


TEMPLATE_FILE = r"Template\template_Table_to_HTML.html"
OUTPUT_DIR = Path("output")
load_external_file = Load_From_External_File()



def generate_html(file_path):

    # OUTPUT_DIR.mkdir(exist_ok=True)
    # OUTPUT_DIR = Path(file_path).parent
    loader = DataLoader()
    df = loader.load(file_path)


    generator = DataTableGenerator(TEMPLATE_FILE)

    # output_file = OUTPUT_DIR / (Path(file_path).stem + ".html")
    output_file = asksaveasfilename(title="Запис", defaultextension=".html", filetypes=[("HTML files", "*.html")])

    if output_file:
        generator.insert_to_html(file_path, df, output_file)

    return output_file

def main():
    # try:
        file_path = load_external_file.select_file()

        if not file_path:
            return

        output_file = generate_html(file_path)

        messagebox.showinfo(
            "Готово",
            f"HTML е генериран:\n{output_file} \n\nМожете да го отворите с браузър или текстов редактор."
        )

    # except Exception as e:
    #     messagebox.showerror("Грешка", str(e))



if __name__ == "__main__":
    main()