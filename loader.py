# loader.py
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from datetime import date, datetime

class FileProcessor:
    def __init__(self):
        self.required_columns = []

    def load_file(self, file_path: str, db_engine=None, connection_string=None, sheet=0) -> pd.DataFrame:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(path, sheet_name=sheet)
        elif suffix == ".csv":
            # Пробваме с различни разделители
            try:
                df = pd.read_csv(path, sep=";", encoding="ANSI")
            except:
                df = pd.read_csv(path, sep=",")
        elif suffix == ".json":
            df = pd.read_json(path)
        elif suffix == ".parquet":
            df = pd.read_parquet(path)
        elif suffix == ".xml":
            df = pd.read_xml(path)
        elif suffix == ".sql":
            # Четене на SQL заявката от файла
            with open(path, 'r', encoding='utf-8') as f:
                query = f.read()
            
            # Избор на engine/connection
            engine = db_engine
            if not engine and connection_string:
                engine = create_engine(connection_string)
            
            if engine:
                df = pd.read_sql(query, engine)
            else:
                raise ValueError("Не е предоставен database engine или connection string за изпълнение на SQL файл.")
        else:
            raise ValueError(f"Не се поддържа този формат: {suffix}")
        
        return df

    def validate_schema(self, df: pd.DataFrame, required_columns: list) -> bool:
        self.required_columns = required_columns
        if not self.required_columns:
            return True
        return all(col in df.columns for col in self.required_columns)

class DataLoader(FileProcessor):
    def load(self, file_path: str, db_engine=None, connection_string=None, params: dict | None = None) -> pd.DataFrame:
        path = Path(file_path)
        if path.suffix.lower() == ".sql" and params is not None:
            return self.load_sql_with_params(file_path, connection_string=connection_string, params=params, db_engine=db_engine)
        return self.load_file(file_path, db_engine=db_engine, connection_string=connection_string)

    @staticmethod
    def _coerce_sql_params(params: dict) -> dict:
        """Подготвя стойности за SQLAlchemy bind параметри."""
        coerced = {}
        for key, value in params.items():
            if isinstance(value, str):
                for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                    try:
                        coerced[key] = datetime.strptime(value, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    coerced[key] = value
            else:
                coerced[key] = value
        return coerced

    def load_sql_with_params(
        self,
        sql_path: str,
        connection_string: str = None,
        params: dict | None = None,
        db_engine=None,
    ) -> pd.DataFrame:
        """Изпълнява SQL файл с параметризирани bind променливи (:name)."""
        with open(sql_path, "r", encoding="utf-8") as f:
            query_text = f.read()

        engine = db_engine
        if not engine and connection_string:
            engine = create_engine(connection_string)

        if not engine:
            raise ValueError("Не е предоставен database engine или connection string.")

        bind_params = self._coerce_sql_params(params or {})
        query = text(query_text)
        return pd.read_sql(query, engine, params=bind_params)