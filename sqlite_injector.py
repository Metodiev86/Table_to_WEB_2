import sqlite3
import pandas as pd
import csv
from datetime import datetime
import traceback

from DataFrame_Handler import DataFrameHandler
from Config import DB_LOG
from query_manager import register_sqlite_user_functions, should_index


class SQLiteInjector:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.table_name = None
        self.handler = DataFrameHandler()

    def _column_index_slug(self, table_name: str, col: str) -> str:
        return "".join(
            ch if ch.isalnum() or ch == "_" else "_"
            for ch in f"{table_name}_{col}".replace(" ", "_")
        )

    def _optimize_dataframe_dtypes(
            self,
            df: pd.DataFrame,
            date_col_names: list
    ):

        for col in df.columns:

            if col in date_col_names:
                continue

        return df

    def _get_connection(self) -> sqlite3.Connection:
        """
        Централизирано създаване на конекция.
        ВАЖНО: locking_mode=EXCLUSIVE е премахнат — несъвместим с WAL при
        повторно отваряне на базата (append сценарий).
        """
        conn = sqlite3.connect(self.db_path)
        register_sqlite_user_functions(conn)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-200000;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        return conn

    def _normalize_dates(self, df: pd.DataFrame):
        """
        Разпознава датови колони, нормализира ги до ISO формат.
        Връща (df_clean, date_col_names) — имена вместо индекси,
        за да са стабилни след евентуален reindex.
        """
        df_clean, date_col_indices, column_metadata = (
            self.handler.detect_date_columns(df)
        )
        date_col_names = [df_clean.columns[i] for i in date_col_indices]
        for col_name in date_col_names:
            dt_series = pd.to_datetime(df_clean[col_name], errors='coerce')
            # timestamp в милисекунди — NaT → pd.NA
            ms = dt_series.astype('int64').where(dt_series.notna(), other=pd.NA)
            df_clean[col_name] = ms.astype("datetime64[ms]").astype("int64")
        return df_clean, date_col_names, column_metadata

    def _sync_indexes_for_columns(
        self,
        conn: sqlite3.Connection,
        cursor: sqlite3.Cursor,
        columns: list,
        date_col_names: list,
        numeric_col_names: list,
        run_analyze: bool = False,   # НОВО: след append задължително → True
    ) -> None:
        """
        Поддържа индексите според типа колона.
        Приема имена на колони (не позиционни индекси) — така е стабилно
        след reindex или промяна на реда на колоните.

        run_analyze=True → изпълнява ANALYZE след пресъздаване на индексите,
        за да актуализира sqlite_stat1 и query planner да вижда новите редове.
        Без това при ORDER BY + LIMIT query planner ползва остарели статистики
        и може да върне грешно сортиран резултат при append сценарий.
        """
        safe_table = f'"{self.table_name}"'

        for col in columns:
            safe_col = col.replace('"', '""')
            idx_slug = self._column_index_slug(self.table_name, col)
            base = f"idx_{idx_slug}"
            try:
                if col in date_col_names:
                    cursor.execute(
                        f'CREATE INDEX IF NOT EXISTS "{base}_date" '
                        f'ON {safe_table} ("{safe_col}")'
                    )
                elif col in numeric_col_names:
                    cursor.execute(
                        f'CREATE INDEX IF NOT EXISTS "{base}_num" '
                        f'ON {safe_table} (CAST("{safe_col}" AS REAL))'
                    )
                else:
                    cursor.execute(
                        f'SELECT COUNT(*), COUNT(DISTINCT "{safe_col}") FROM {safe_table}'
                    )
                    total, distinct = cursor.fetchone()
                    total = total or 0
                    distinct = distinct or 0
                    cursor.execute(
                        f"SELECT COALESCE(MAX(cnt), 0) FROM "
                        f'(SELECT COUNT(*) AS cnt FROM {safe_table} GROUP BY "{safe_col}")'
                    )
                    top_freq = int(cursor.fetchone()[0] or 0)
                    lower_name = f"{base}_lower"
                    if should_index(total, distinct, top_freq):
                        cursor.execute(
                            f'CREATE INDEX IF NOT EXISTS "{lower_name}" '
                            f'ON {safe_table} (LOWER("{safe_col}"))'
                        )
                    else:
                        cursor.execute(f'DROP INDEX IF EXISTS "{lower_name}"')
            except Exception as e:
                print(f"Внимание: индекс за {col!r}: {e}")

        # ── FIX: Актуализира статистиките на query planner след append ──────
        # ANALYZE обновява sqlite_stat1 така че SQLite да знае реалния брой
        # редове и разпределение на стойностите — критично за правилен
        # ORDER BY + LIMIT при нарастваща таблица.
        if run_analyze:
            try:
                cursor.execute(f"ANALYZE {safe_table}")
            except Exception as e:
                print(f"Внимание: ANALYZE неуспешен: {e}")

    def db_log(self, message: str):
        with open(DB_LOG, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([datetime.now().isoformat(), self.db_path, self.table_name, message])

    def create_table_from_df(self, df: pd.DataFrame, table_name: str):
        self.table_name = table_name
        conn = self._get_connection()
        df.head(0).to_sql(self.table_name, conn, if_exists='replace', index=False)
        conn.close()

    def inject_data(self, df: pd.DataFrame, table_name: str):
        self.table_name = table_name
        self.db_log(f"🔄 Започване на ПЪЛЕН rebuild на '{self.table_name}' ({len(df)} реда)...")

        (df_clean, date_col_names, column_metadata) = self._normalize_dates(df)

        df_clean = self._optimize_dataframe_dtypes(
            df_clean,
            date_col_names
        )

        # ── FIX: Закръгляване ПРЕДИ to_sql, не след него ────────────────────
        # Оригиналният код закръгляваше df_clean след като вече беше записан
        # в базата — тоест базата съдържаше некръглени стойности.
        _, numeric_col_names = self._get_numeric_col_names(df_clean)
        df_clean = self.handler.round_numeric_columns(df_clean, numeric_col_names)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            df_clean.to_sql(self.table_name, conn, if_exists='replace', index=False, chunksize=5000)

            self._sync_indexes_for_columns(
                conn, cursor, list(df_clean.columns), date_col_names, numeric_col_names,
                run_analyze=False,   # При пълен rebuild ANALYZE не е нужен —
                                     # to_sql replace нулира статистиките сам.
            )

            conn.commit()
            self.db_log(f"🚀 Успешно пресъздаване на '{self.table_name}'.")

        except Exception as e:
            conn.rollback()
            self.db_log(f"❌ Грешка при rebuild на SQLite: {e}")
            print(f"❌ Грешка при инжектиране в SQLite: {e}")
        finally:
            conn.close()

    def append_data(self, df: pd.DataFrame, table_name: str):
        """
        Добавя нови записи към съществуваща таблица.
        Ако таблицата липсва, създава я (без full replace).
        """
        self.table_name = table_name
        self.db_log(f"➕ Започване на APPEND към '{self.table_name}' ({len(df)} нови реда)...")

        # 1. Нормализация на дати — запазваме ИМЕНА, не индекси
        (df_clean, date_col_names, column_metadata) = self._normalize_dates(df)

        df_clean = self._optimize_dataframe_dtypes(
            df_clean,
            date_col_names
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (self.table_name,)
            )
            table_exists = cursor.fetchone() is not None

            if table_exists:
                safe_table = self.table_name.replace('"', '""')
                cursor.execute(f'PRAGMA table_info("{safe_table}")')
                existing_cols = [row[1] for row in cursor.fetchall()]

                if not existing_cols:
                    raise ValueError(f"Таблицата '{self.table_name}' е без валидна схема.")

                incoming_cols = list(df_clean.columns)
                extra_cols = [c for c in incoming_cols if c not in existing_cols]
                missing_cols = [c for c in existing_cols if c not in incoming_cols]

                if extra_cols:
                    self.db_log(f"ℹ️ Append: пропуснати нови колони (не съществуват в DB): {extra_cols}")
                if missing_cols:
                    self.db_log(f"ℹ️ Append: липсващи колони, добавени като празни: {missing_cols}")

                # reindex подравнява колоните към схемата на базата
                df_clean = df_clean.reindex(columns=existing_cols)

                # ВАЖНО: след reindex преизчисляваме date_col_names спрямо
                # новия ред на колоните (extra_cols са вече изключени)
                date_col_names = [c for c in date_col_names if c in existing_cols]

            # ── FIX: Закръгляване ПРЕДИ to_sql, не след него ────────────────
            # Оригиналният код закръгляваше df_clean след as вече беше записан
            # в базата — тоест базата съдържаше некръглени стойности.
            _, numeric_col_names = self._get_numeric_col_names(df_clean)
            df_clean = self.handler.round_numeric_columns(df_clean, numeric_col_names)

            # 2. Записване
            df_clean.to_sql(self.table_name, conn, if_exists='append', index=False, chunksize=5000)

            # 3. Индекси + ANALYZE (задължителен при append!)
            self._sync_indexes_for_columns(
                conn, cursor, list(df_clean.columns), date_col_names, numeric_col_names,
                run_analyze=True,    # ← КЛЮЧОВАТА КОРЕКЦИЯ:
                                     # Актуализира sqlite_stat1 → query planner
                                     # вижда новите редове при ORDER BY + LIMIT.
                                     # Без това сортирането по дата в DESC режим
                                     # връща максимума от първоначалния rebuild,
                                     # игнорирайки append-натите записи.
            )

            conn.commit()
            status = "APPEND" if table_exists else "СЪЗДАВАНЕ"
            self.db_log(f"✅ Успешен {status} към '{self.table_name}'.")

        except Exception as e:
            conn.rollback()
            tb = traceback.format_exc(limit=10)
            self.db_log(f"❌ Грешка при append в SQLite: {e!r}")
            self.db_log(f"❌ Traceback: {tb}")
            print(f"❌ Грешка при append в SQLite: {e!r}")
        finally:
            conn.close()

    def _get_numeric_col_names(self, df: pd.DataFrame):
        """
        Връща (индекси, имена) на числовите колони.
        Централизирано, за да не се повтаря логиката.
        """
        numeric_indices, _ = self.handler.detect_numeric_columns(df)
        numeric_names = [df.columns[i] for i in numeric_indices]
        return numeric_indices, numeric_names
