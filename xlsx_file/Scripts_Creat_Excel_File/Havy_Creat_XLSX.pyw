# main.py
from Master_Creater_SQL_to_XLSX import XLSX_SCRIPT
import subprocess

scripts = [
    rf"{XLSX_SCRIPT}/Касова Книга Архив_xlsx.py",
    rf"{XLSX_SCRIPT}/Разплащания АРХИВ_xlsx.py",
    rf"{XLSX_SCRIPT}/Продажби по Оператори АРХИВ_xlsx.py",
    rf"{XLSX_SCRIPT}/Вземания от Партньори_xlsx.py"
]

for script in scripts:
    result = subprocess.run(["python", script])
    

    if result.returncode != 0:
        print(f"Error in {script}")
        break