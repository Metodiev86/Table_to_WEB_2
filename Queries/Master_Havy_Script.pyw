# main.py
import subprocess
from Querry_Temp import XLSX_DIR, QUERY_DIR, XLSX_SCRIPT

scripts = [
    rf"{QUERY_DIR}\Касова Книга Архив.pyw",
    rf"{QUERY_DIR}\Разплащания Архив.pyw",
    rf"{QUERY_DIR}\Продажби по Оператори АРХИВ.pyw",
    rf"{QUERY_DIR}\Разлика Доставна Архив.pyw",
    rf"{QUERY_DIR}\Разлика Доставна Вчера.pyw",

]

for script in scripts:
    result = subprocess.run(["python", script])

    if result.returncode != 0:
        print(f"Error in {script}")
        break