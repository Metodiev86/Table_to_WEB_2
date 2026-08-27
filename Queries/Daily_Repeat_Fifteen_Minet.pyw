# main.py
import subprocess
from Querry_Temp import XLSX_DIR, QUERY_DIR, XLSX_SCRIPT

scripts = [
    rf"{QUERY_DIR}\Аванс за Стока.pyw",
    rf"{QUERY_DIR}\Аванс за Стока КОДИМА.pyw",
]

for script in scripts:
    result = subprocess.run(["pythonw", script])

    if result.returncode != 0:
        print(f"Error in {script}")
        break