# main.py
import subprocess
from Querry_Temp import XLSX_DIR, QUERY_DIR, XLSX_SCRIPT

scripts = [
    rf"{QUERY_DIR}\Вземания от Партньори_по_Фактура.pyw",
    rf"{QUERY_DIR}\Вземания от Партньори.pyw",
    rf"{QUERY_DIR}\Вземания - Tранспорт BG.pyw",
    rf"{QUERY_DIR}\Вземания - Tранспорт EU.pyw",
    rf"{QUERY_DIR}\Просрочия по Дни.pyw"
]

for script in scripts:
    result = subprocess.run(["pythonw", script])

    if result.returncode != 0:
        print(f"Error in {script}")
        break