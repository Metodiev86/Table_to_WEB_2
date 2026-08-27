import pandas as pd
import sys
sys.path.append(r"D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2")  # Добавяме родителската папка към пътя за импортиране
from db_config import MSSQL_CONN_STR, create_engine
from report_template import toast_message_end, XLSX_DIR, XLSX_SCRIPT


def engine_from_connection_string(con_string=MSSQL_CONN_STR):
    engine = create_engine(con_string)
    return engine

def create_df(query: str, engine):
    df = pd.read_sql_query(query, engine)
    return df

def export_to_excel(df: pd.DataFrame, path: str):
    df.to_excel(path, index=False)
    toast_message_end(path)

my_engine = engine_from_connection_string()

