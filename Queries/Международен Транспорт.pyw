from Querry_Temp import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private
from pathlib import Path
file_in = Path(r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\ТРАНСПОРТ ОБЩО\2026\Международен Транспорт.xlsx")
file_out = Path(fr"{OUTPUT_DIR_Public}/Международен Транспорт.html")

generate_report(file_in, file_out, category="Транспорт")
