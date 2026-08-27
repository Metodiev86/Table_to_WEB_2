from Querry_Temp import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private, OUTPUT_DIR_SECRET,  XLSX_DIR, SQL_SCRIPTS_PATH, KODIMA_CONN_STR
from pathlib import Path

file_in = Path(rf"{SQL_SCRIPTS_PATH}\АВАНС_ЗА_СТОКА_КОДИМА.sql")
file_out = Path(fr"{OUTPUT_DIR_SECRET}/АВАНС ЗА СТОКА - КОДИМА.html")

generate_report(file_in, file_out,  category="КОДИМА", conn_str=KODIMA_CONN_STR)
