# db_config.py
from sqlalchemy import create_engine
import os

USER = os.getenv("DB_USERNAME")
PASSWORD = os.getenv("DB_PASSWORD")

# Connection Strings
MSSQL_CONN_STR = f"mssql+pyodbc://{USER}:{PASSWORD}@192.168.50.100/StabiDi_Original?driver=ODBC+Driver+17+for+SQL+Server"
KODIMA_CONN_STR = f"mssql+pyodbc://{USER}:{PASSWORD}@192.168.50.100/Kodima?driver=ODBC+Driver+17+for+SQL+Server"

# Engines
# Тук можете да дефинирате готови engine обекти, ако е необходимо
def get_engine(conn_str):
    return create_engine(conn_str)

# Пример за конфигурация, която ще се подава на метода за зареждане
DEFAULT_DB_CONFIG = {
    "engine": None,  # Ще се създаде при поискване или се подава директно
    "connection_string": MSSQL_CONN_STR
}
