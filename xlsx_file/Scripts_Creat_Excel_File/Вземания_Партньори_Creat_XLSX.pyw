# main.py
import subprocess
from Master_Creater_SQL_to_XLSX import XLSX_SCRIPT
scripts = [
    rf"{XLSX_SCRIPT}\Вземания от Партньори_по_Фактура_xlsx.py",
    rf"{XLSX_SCRIPT}\Вземания от Партньори_xlsx.py",
    rf"{XLSX_SCRIPT}\Вземания Транспорт_BG_xlsx.py",
    rf"{XLSX_SCRIPT}\Вземания Транспорт_EU_xlsx.py",
    
]

for script in scripts:
    result = subprocess.run(["python", script])

    if result.returncode != 0:
        print(f"Error in {script}")
        break
