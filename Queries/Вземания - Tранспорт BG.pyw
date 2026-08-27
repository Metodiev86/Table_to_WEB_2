from Querry_Temp import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private, XLSX_DIR, SQL_SCRIPTS_PATH, MSSQL_CONN_STR
from pathlib import Path

file_in = Path(rf"{SQL_SCRIPTS_PATH}\Вземания Транспорт_BG.sql")
file_out = Path(fr"{OUTPUT_DIR_Private}\Вземания - Tранспорт BG.html")

generate_report(file_in, file_out,  category="Просрочия", conn_str =MSSQL_CONN_STR)
