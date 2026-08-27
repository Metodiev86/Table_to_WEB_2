import sys
from pathlib import Path
sys.path.append(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2")  # Добавяме родителската папка към пътя за импортиране
from Config import SQL_SCRIPTS_PATH, OUTPUT_DIR_SECRET
from db_config import  MSSQL_CONN_STR, KODIMA_CONN_STR
from  report_template import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private, XLSX_DIR, QUERY_DIR, XLSX_SCRIPT, SQL_SCRIPTS_PATH

# --- Пример за генериране на отчет с категория ---
if __name__ == "__main__":
    # 1. Дефинираме пътищата
    input_file = Path(r"data\sample_data.xlsx") # Променете според вашите нужди
    output_file = OUTPUT_DIR_Public / "new_report.html"
    
    # 2. Подаваме и категория
    generate_report(input_file, output_file, category="Финанси")


