from math import trunc

from Querry_Temp import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private, XLSX_DIR, SQL_SCRIPTS_PATH, MSSQL_CONN_STR
from pathlib import Path
file_in = Path(rf"{SQL_SCRIPTS_PATH}\Продажби по Оператори АРХИВ.sql")
file_out = Path(fr"{OUTPUT_DIR_Public}/Продажби по Оператори АРХИВ.html")

generate_report(file_in, file_out,"Справки", MSSQL_CONN_STR, is_rebuild=True, is_dinamic=True)