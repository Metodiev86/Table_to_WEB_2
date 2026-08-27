from Querry_Temp import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private
from pathlib import Path
file_in = Path(r"D:\SynologyDrive\ОФИС\СПОДЕЛЕНИ\ЗАЯВКИ ЗА ДОСТАВКА\СНАБДЯВАНЕ.xlsx")
file_out = Path(fr"{OUTPUT_DIR_Public}/Заявки за Доставка.html")
generate_report(file_in, file_out, "Справки")