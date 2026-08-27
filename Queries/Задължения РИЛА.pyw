from Querry_Temp import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private
from pathlib import Path
file_in = Path(r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\Задължения Доставчици\РИЛА Текущи задължения към Доставчици.xlsx")
file_out = Path(fr"{OUTPUT_DIR_Private}/Задължения РИЛА.html")
generate_report(file_in, file_out, "Задължения")