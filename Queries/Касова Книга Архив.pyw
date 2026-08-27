from Querry_Temp import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private, XLSX_DIR, SQL_SCRIPTS_PATH, MSSQL_CONN_STR
from pathlib import Path
import pandas as pd
import sys
sys.path.append(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2")


file_in = Path(rf"{SQL_SCRIPTS_PATH}\Касова Книга АРХИВ.sql")
file_out = Path(fr"{OUTPUT_DIR_Public}/Касова Книга АРХИВ.html")

generate_report(file_in, file_out,"Разплащания", conn_str=MSSQL_CONN_STR, is_rebuild=False, is_dinamic = True)