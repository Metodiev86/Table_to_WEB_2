from pathlib import Path

TEMPLATE_FILE_PATH = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\Template\template_Table_to_HTML.html")
OUTPUT_DIR_Public = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\output")
OUTPUT_DIR_Private = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\private_output")
OUTPUT_DIR_SECRET = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\secret_output")
DB_DIR = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\databases")
LOG_DIR = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\logs")
METADATA_DIR = Path(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\metadata")
QUERY_DIR = r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\Queries"
XLSX_DIR = r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\xlsx_file"
XLSX_SCRIPT = rf"{XLSX_DIR}/Scripts_Creat_Excel_File"
SQL_SCRIPTS_PATH = r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\Queries\SQL_SCRIPTS"
OUTPUT_DIR_Public.mkdir(exist_ok=True)
OUTPUT_DIR_Private.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)

SUCCESS_LOG = LOG_DIR / "success_log.csv"
ERROR_LOG = LOG_DIR / "error_log.csv"
DB_LOG = LOG_DIR / "db_log.csv"