from Querry_Temp import generate_report, OUTPUT_DIR_Public, OUTPUT_DIR_Private, SQL_SCRIPTS_PATH
from pathlib import Path
file_in = Path(rf"{SQL_SCRIPTS_PATH}\Артикули Код.sql")
file_out = Path(fr"{OUTPUT_DIR_Public}\Артикули Код.html")
generate_report(file_in, file_out, category="Номенклатури")