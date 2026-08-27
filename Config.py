from pathlib import Path

# Взема папката, в която се намира настоящият .py файл
BASE_DIR = Path(__file__).resolve().parent

# Относителни пътища спрямо BASE_DIR
TEMPLATE_FILE_PATH = BASE_DIR / "Template" / "template_Table_to_HTML.html"
OUTPUT_DIR_Public = BASE_DIR / "output"
OUTPUT_DIR_Private = BASE_DIR / "private_output"
OUTPUT_DIR_SECRET = BASE_DIR / "secret_output"
DB_DIR = BASE_DIR / "databases"
LOG_DIR = BASE_DIR / "logs"
METADATA_DIR = BASE_DIR / "metadata"

QUERY_DIR = BASE_DIR / "Queries"
XLSX_DIR = BASE_DIR / "xlsx_file"
XLSX_SCRIPT = XLSX_DIR / "Scripts_Creat_Excel_File"
SQL_SCRIPTS_PATH = QUERY_DIR / "SQL_SCRIPTS"

# Създаване на директориите при нужда
OUTPUT_DIR_Public.mkdir(exist_ok=True)
OUTPUT_DIR_Private.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)

# Лог файлове
SUCCESS_LOG = LOG_DIR / "success_log.csv"
ERROR_LOG = LOG_DIR / "error_log.csv"
DB_LOG = LOG_DIR / "db_log.csv"

