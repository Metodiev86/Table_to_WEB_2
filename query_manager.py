import sqlite3
import sys
import pandas as pd
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


def should_index(total: int, distinct: int, top_freq: int) -> bool:
    """Връща True, когато колоната си струва текстов (expression) индекс по LOWER."""
    if total <= 0:
        return False
    if distinct < 20:
        return False
    if distinct / total < 0.01:
        return False
    if top_freq / total > 0.3:
        return False
    return True


def register_sqlite_user_functions(conn: sqlite3.Connection) -> None:
    """Регистрира същите UDF като при заявките, за да съвпадат с expression индексите."""
    def _create_function(name, narg, func):
        if sys.version_info >= (3, 8):
            conn.create_function(name, narg, func, deterministic=True)
        else:
            conn.create_function(name, narg, func)

    _create_function("LOWER", 1, lambda x: str(x).lower() if x is not None else None)

    def date_iso(val):
        if not val:
            return ""
        s = str(val).strip()
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
        if "." in s:
            parts = s.split(".")
            if len(parts) >= 3:
                d, m, y = parts[0].strip(), parts[1].strip(), parts[2].strip()[:4]
                return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        if "/" in s:
            parts = s.split("/")
            if len(parts) >= 3:
                d, m, y = parts[0].strip(), parts[1].strip(), parts[2].strip()[:4]
                return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        if "/" in s and s.index("/") == 4:
            return s.replace("/", "-")[:10]
        return s

    _create_function("DATE_ISO", 1, date_iso)


class QueryManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._init_index_meta()

    def _init_index_meta(self):
        """Създава таблица за проследяване на използването на индексите"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS index_usage (
                    index_name TEXT PRIMARY KEY,
                    table_name TEXT,
                    columns TEXT,
                    created_at DATETIME,
                    last_used DATETIME
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _iso_to_ts_ms(self, iso_str: str) -> int | None:
        """Конвертира ISO дата '2024-05-06' към Unix timestamp в милисекунди."""
        if not iso_str or not str(iso_str).strip():
            return None
        try:
            dt = datetime.strptime(str(iso_str).strip()[:10], '%Y-%m-%d')
            return int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            return None


    def _get_connection(self):
        """Връща връзка към базата с регистрирана поддръжка за кирилица и нормализация на дати"""
        conn = sqlite3.connect(self.db_path)
        # WAL mode за асинхронно писане/четене
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        register_sqlite_user_functions(conn)
        return conn

    def get_table_headers(self, table_name: str) -> list:
        """Връща подреден списък с имената на колоните за дадена таблица."""
        safe_table = table_name.replace('"', '""')
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA table_info("{safe_table}")')
            return [row[1] for row in cursor.fetchall()]
        finally:
            conn.close()

    def _create_index_async(self, table: str, columns: list):
        if not columns: return
        self.executor.submit(self._create_index_safe, table, columns)

    def _create_index_safe(self, table: str, columns: list):
        try:
            safe_table = table.replace('"', '""')
            col_slug = "_".join(re.sub(r'\W+', '_', c) for c in columns)
            index_name = f"idx_group_{col_slug}"[:60] # Ограничение за дължина
            
            conn = self._get_connection()
            try:
                # 1. Проверка за лимит (MAX 10 индекса)
                cursor = conn.cursor()
                cursor.execute("SELECT index_name FROM index_usage WHERE table_name = ? ORDER BY last_used ASC", (table,))
                existing = cursor.fetchall()
                
                if len(existing) >= 10:
                    oldest = existing[0][0]
                    cursor.execute(f'DROP INDEX IF EXISTS "{oldest}"')
                    cursor.execute("DELETE FROM index_usage WHERE index_name = ?", (oldest,))
                
                # 2. Създаване на индекс
                cols_sql = ", ".join([f'"{c.replace("\"", "\"\"")}"' for c in columns])
                cursor.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{safe_table}" ({cols_sql})')
                
                # 3. Обновяване на метаданни
                now = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO index_usage (index_name, table_name, columns, created_at, last_used)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(index_name) DO UPDATE SET last_used = excluded.last_used
                """, (index_name, table, json.dumps(columns), now, now))
                
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"[INDEX ERROR] {e}")

    def _parse_sb_criteria(self, criteria_list, logic='AND', active_groups=None, table_name=None, subtotal_filters=None, prefix=None):
        clauses = []
        for c in criteria_list:
            if 'logic' in c:
                # Nested group
                sub_clause = self._parse_sb_criteria(c['criteria'], c['logic'], active_groups, table_name, subtotal_filters, prefix)
                if sub_clause:
                    clauses.append(f"({sub_clause})")
            else:
                # Leaf condition
                col = c.get('data')
                cond = c.get('condition')
                val_raw = c.get('value', [])
                ctype = c.get('type', 'string')
                
                # Normalize value to list
                val = val_raw if isinstance(val_raw, list) else [val_raw]
                
                if not col or not cond: continue
                
                # Safely quote column name
                safe_col = str(col).replace('"', '""')
                col_sql = f'"{safe_col}"'
                if prefix:
                    col_sql = f'{prefix}."{safe_col}"'

                if ctype == 'date':
                    # стойностите идват като ISO стринг от SearchBuilder → конвертирай към ms
                    def date_val(v):
                        ts = self._iso_to_ts_ms(v)
                        return str(ts) if ts is not None else None

                    if cond in ('=', 'equals'):
                        ts = date_val(val[0])
                        if ts:
                            clauses.append(f"{col_sql} = {ts}")
                    elif cond in ('!=', 'not'):
                        ts = date_val(val[0])
                        if ts:
                            clauses.append(f"{col_sql} != {ts}")
                    elif cond in ('<', 'before', '<='):
                        ts = date_val(val[0])
                        if ts:
                            clauses.append(f"{col_sql} <= {ts}")
                    elif cond in ('>', 'after', '>='):
                        ts = date_val(val[0])
                        if ts:
                            clauses.append(f"{col_sql} >= {ts}")
                    elif cond == 'between':
                        ts1 = date_val(val[0]) if len(val) > 0 else None
                        ts2 = date_val(val[1]) if len(val) > 1 else None
                        if ts1 and ts2:
                            clauses.append(f"{col_sql} BETWEEN {ts1} AND {ts2}")
                        elif ts1:
                            clauses.append(f"{col_sql} >= {ts1}")
                        elif ts2:
                            clauses.append(f"{col_sql} <= {ts2}")
                    elif cond == 'notBetween':
                        ts1 = date_val(val[0]) if len(val) > 0 else None
                        ts2 = date_val(val[1]) if len(val) > 1 else None
                        if ts1 and ts2:
                            clauses.append(f"{col_sql} NOT BETWEEN {ts1} AND {ts2}")
                    elif cond in ('null', 'empty'):
                        clauses.append(f'({col_sql} IS NULL OR {col_sql} = "")')
                    elif cond in ('!null', 'notEmpty'):
                        clauses.append(f'({col_sql} IS NOT NULL AND {col_sql} != "")')
                    continue  # ← важно: skip общия блок по-долу
                
                # Helper to escape values
                def esc(v):
                    return str(v).replace("'", "''")

                # Subtotal filtering logic
                if cond in ('subtotal_gt', 'subtotal_lt', 'subtotal_gte', 'subtotal_lte', 'subtotal_eq', 'subtotal_neq') and active_groups and table_name:
                    if subtotal_filters is not None:
                        subtotal_filters.append({
                            'measure': col,
                            'condition': cond,
                            'value': float(val[0]) if val[0] else 0
                        })
                        continue # Ще се обработи чрез CTE
                    
                    # Fallback към correlated subquery ако не ползваме CTE
                    group_col = active_groups[-1]
                    safe_group_col = str(group_col).replace('"', '""')
                    safe_table = str(table_name).replace('"', '""')
                    
                    subquery = (
                        f'(SELECT SUM(COALESCE(CAST("{safe_col}" AS REAL), 0)) FROM "{safe_table}" t2 '
                        f'WHERE COALESCE(t2."{safe_group_col}", \'\') = COALESCE("{safe_table}"."{safe_group_col}", \'\'))'
                    )
                    
                    op_map = {
                        'subtotal_gt': '>',
                        'subtotal_lt': '<',
                        'subtotal_gte': '>=',
                        'subtotal_lte': '<=',
                        'subtotal_eq': '=',
                        'subtotal_neq': '!='
                    }
                    sql_op = op_map.get(cond, '>')
                    clauses.append(f"{subquery} {sql_op} {esc(val[0])}")
                    continue

                # Operators mapping
                if cond == '=' or cond == 'equals' or cond == 'null':
                    if len(val) > 0 and val[0] is not None:
                        clauses.append(f"{col_sql} = '{esc(val[0])}'")
                elif cond == '!=' or cond == 'not':
                    if len(val) > 0 and val[0] is not None:
                        clauses.append(f"{col_sql} != '{esc(val[0])}'")
                elif cond == '<' or cond == 'before':
                    if len(val) > 0 and val[0] is not None:
                        clauses.append(f"{col_sql} <= '{esc(val[0])}'")
                elif cond == '<=':
                    if len(val) > 0 and val[0] is not None:
                        clauses.append(f"{col_sql} <= '{esc(val[0])}'")
                elif cond == '>' or cond == 'after':
                    if len(val) > 0 and val[0] is not None:
                        clauses.append(f"{col_sql} >= '{esc(val[0])}'")
                elif cond == '>=':
                    if len(val) > 0 and val[0] is not None:
                        clauses.append(f"{col_sql} >= '{esc(val[0])}'")
                elif cond == 'between':
                    v1 = val[0] if len(val) > 0 else None
                    v2 = val[1] if len(val) > 1 else None
                    # Handle cases where one or both are empty
                    if v1 is not None and v2 is not None and str(v1).strip() != "" and str(v2).strip() != "":
                        clauses.append(f"{col_sql} BETWEEN '{esc(v1)}' AND '{esc(v2)}'")
                    elif v1 is not None and str(v1).strip() != "":
                        clauses.append(f"{col_sql} >= '{esc(v1)}'")
                    elif v2 is not None and str(v2).strip() != "":
                        clauses.append(f"{col_sql} <= '{esc(v2)}'")
                elif cond == 'notBetween':
                    if len(val) >= 2:
                        clauses.append(f"{col_sql} NOT BETWEEN '{esc(val[0])}' AND '{esc(val[1])}'")
                elif cond == 'startsWith':
                    if len(val) > 0 and val[0] is not None:
                        clauses.append(f"LOWER({col_sql}) LIKE '{esc(val[0]).lower()}%'")
                elif cond == 'contains' or cond == 'string':
                    if len(val) > 0 and val[0] is not None:
                        ev = esc(val[0]).lower()
                        if ctype == 'string':
                            clauses.append(f"LOWER({col_sql}) LIKE '{ev}%'")
                        else:
                            clauses.append(f"LOWER({col_sql}) LIKE '%{ev}%'")
                elif cond == 'endsWith':
                    if len(val) > 0 and val[0] is not None:
                        clauses.append(f"LOWER({col_sql}) LIKE '%{esc(val[0]).lower()}'")
                elif cond == 'null' or cond == 'empty':
                    if ctype in ('num', 'num-fmt'):
                        clauses.append(
                            f'("{safe_col}" IS NULL OR TRIM(COALESCE(CAST("{safe_col}" AS TEXT), \'\')) = \'\')'
                        )
                    else:
                        clauses.append(f'({col_sql} IS NULL OR {col_sql} = \'\')')
                elif cond == '!null' or cond == 'notEmpty':
                    if ctype in ('num', 'num-fmt'):
                        clauses.append(
                            f'("{safe_col}" IS NOT NULL AND TRIM(COALESCE(CAST("{safe_col}" AS TEXT), \'\')) != \'\')'
                        )
                    else:
                        clauses.append(f'({col_sql} IS NOT NULL AND {col_sql} != \'\')')
        
        if not clauses: return ""
        return f" {logic} ".join(clauses)

    def _build_where_clauses(self, filters, search_value, text_columns, active_groups=None, table_name=None, subtotal_filters=None, prefix=None):
        where_clauses = []
        
        # 1. SearchBuilder (SB) Priority
        if filters and 'sb' in filters:
            try:
                sb_state = filters['sb']
                if isinstance(sb_state, str) and sb_state.strip():
                    sb = json.loads(sb_state)
                elif isinstance(sb_state, dict):
                    sb = sb_state
                else:
                    sb = None
                    
                if sb and 'criteria' in sb:
                    sb_sql = self._parse_sb_criteria(sb['criteria'], sb.get('logic', 'AND'), active_groups, table_name, subtotal_filters, prefix)
                    if sb_sql:
                        where_clauses.append(f"({sb_sql})")
            except Exception as e:
                print(f"SB Parse Error: {e}")

        # 2. Column Filter (Dropdowns / Legacy)
        if filters:
            for col, val in filters.items():
                if not val or col in ('sb', 'numeric_columns', 'date_columns', 'text_columns', 'limit', 'offset', 'sort_by', 'search'):
                    continue
                
                # Quoting column names safely
                safe_col = col.replace('"', '""')
                col_sql = f'"{safe_col}"'
                if prefix:
                    col_sql = f'{prefix}."{safe_col}"'
                
                # Handle dropdown multiple values (separated by |)
                if isinstance(val, list) or "|" in str(val):
                    vals = val if isinstance(val, list) else str(val).split("|")
                    # Нормализираме стойностите: трим + lower, за да съвпадат с TRIM(LOWER(...)) в SQL
                    norm_vals = [str(v).strip().lower().replace("'", "''") for v in vals if str(v).strip() != ""]
                    if norm_vals:
                        placeholders = ", ".join([f"'{nv}'" for nv in norm_vals])
                        where_clauses.append(f'TRIM(LOWER({col_sql})) IN ({placeholders})')
                elif not col.endswith(("_min", "_max", "_date_min", "_date_max")):
                    # Column filter - exact match; нормализираме и двете страни с TRIM + LOWER
                    safe_val = str(val).strip().lower().replace("'", "''")
                    if safe_val != "":
                        where_clauses.append(f'TRIM(LOWER({col_sql})) = \'{safe_val}\'')
        
        # 3. Global Search (само текстови колони; префиксно съвпадение за ползване на LOWER индекси)
        if search_value and text_columns:
            search_clauses = []
            lower_search = str(search_value).lower().replace("'", "''")
            for col in text_columns:
                if not col:
                    continue
                safe_col = col.replace('"', '""')
                col_sql = f'"{safe_col}"'
                if prefix:
                    col_sql = f'{prefix}."{safe_col}"'
                search_clauses.append(f'LOWER({col_sql}) LIKE \'{lower_search}%\'')
            if search_clauses:
                where_clauses.append("(" + " OR ".join(search_clauses) + ")")
                
        return where_clauses

    def _normalize_order_by(
        self,
        sort_by: str,
        safe_table: str,
        numeric_column_indices: list,
        date_column_indices: list,
        table_alias: str = None,
    ) -> str:
        """ORDER BY с CAST/DATE_ISO/LOWER според типа, за съвместимост с индексите."""
        if not sort_by or not sort_by.strip():
            return ""
        s = sort_by.strip()
        m = re.match(r'^"((?:[^"]|"")*)"\s+(ASC|DESC)\s*$', s, re.I)
        if not m:
            return f" ORDER BY {sort_by}"
        col_name = m.group(1).replace('""', '"')
        direction = m.group(2).upper()
        safe_col = col_name.replace('"', '""')

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA table_info("{safe_table}")')
            headers = [row[1] for row in cursor.fetchall()]
        finally:
            conn.close()

        if col_name not in headers:
            return f" ORDER BY {sort_by}"

        idx = headers.index(col_name)
        qualified_col = f'"{safe_col}"'
        if table_alias:
            safe_alias = table_alias.replace('"', '""')
            qualified_col = f'{safe_alias}."{safe_col}"'

        if idx in numeric_column_indices:
            expr = f"CAST({qualified_col} AS REAL)"
        elif idx in date_column_indices:
            expr = qualified_col
        else:
            expr = f"LOWER({qualified_col})"
        return f" ORDER BY {expr} {direction}"

    def build_dynamic_query(self, table_name: str, filters: dict = None, sort_by: str = None, 
                           search_value: str = None, text_columns: list = None, 
                           limit: int = 1000, offset: int = 0, sb_state: str = None,
                           numeric_column_indices: list = None, date_column_indices: list = None) -> tuple:
        
        # Use common builder
        all_filters = (filters or {}).copy()
        if sb_state: all_filters['sb'] = sb_state
        
        headers = self.get_table_headers(table_name)

        # Extract active groups if present
        active_groups = None
        ag_idx_raw = all_filters.pop('active_group_indices', None)
        if ag_idx_raw:
            try:
                idx_list = [int(x) for x in str(ag_idx_raw).split(',') if str(x).strip() != ""]
                resolved = [headers[i] for i in idx_list if 0 <= i < len(headers)]
                if resolved:
                    active_groups = resolved
            except Exception:
                pass
        if all_filters and 'active_groups' in all_filters:
            ag_raw = all_filters.pop('active_groups')
            if ag_raw and not active_groups:
                active_groups = ag_raw.split('|')
        
        # Филтър по междинни суми от custom UI (извън SearchBuilder)
        subtotal_ui_col = all_filters.pop('subtotal_ui_col', None)
        subtotal_ui_col_idx = all_filters.pop('subtotal_ui_col_idx', None)
        if subtotal_ui_col_idx is not None and str(subtotal_ui_col_idx).strip() != "":
            try:
                i = int(subtotal_ui_col_idx)
                if 0 <= i < len(headers):
                    subtotal_ui_col = headers[i]
            except Exception:
                pass
        subtotal_ui_op = all_filters.pop('subtotal_ui_op', None)
        subtotal_ui_value = all_filters.pop('subtotal_ui_value', None)
        
        subtotal_filters = []
        where_clauses = self._build_where_clauses(all_filters, search_value, text_columns, active_groups, table_name, subtotal_filters)
        if subtotal_ui_col and subtotal_ui_op and subtotal_ui_value not in (None, "") and active_groups:
            try:
                subtotal_filters.append({
                    "measure": str(subtotal_ui_col),
                    "condition": str(subtotal_ui_op),
                    "value": float(subtotal_ui_value)
                })
            except Exception:
                pass
        
        # Safely quote table name
        safe_table = table_name.replace('"', '""')

        # 4. Unique/Duplicate filters
        unique_filters = all_filters.get('unique_filters')
        if unique_filters:
            try:
                uf = json.loads(unique_filters)
                conn = self._get_connection()
                for col_idx_str, action in uf.items():
                    col_idx = int(col_idx_str)
                    cursor = conn.cursor()
                    cursor.execute(f'PRAGMA table_info("{safe_table}")')
                    headers = [row[1] for row in cursor.fetchall()]
                    if col_idx < len(headers):
                        col_name = headers[col_idx]
                        safe_cn = col_name.replace('"', '""')
                        
                        if action == 'duplicates':
                            where_clauses.append(f'"{safe_cn}" IN (SELECT "{safe_cn}" FROM "{safe_table}" GROUP BY "{safe_cn}" HAVING COUNT(*) > 1)')
                        elif action == 'uniques':
                            where_clauses.append(f'"{safe_cn}" IN (SELECT "{safe_cn}" FROM "{safe_table}" GROUP BY "{safe_cn}" HAVING COUNT(*) = 1)')
                        elif action == 'first-seen':
                            where_clauses.append(f'rowid IN (SELECT MIN(rowid) FROM "{safe_table}" GROUP BY "{safe_cn}")')
                conn.close()
            except Exception as e:
                print(f"Unique Filter Error: {e}")

        where_sql = ""
        if where_clauses:
            where_sql = " WHERE " + " AND ".join(where_clauses)
            
        num_idx = numeric_column_indices or []
        date_idx = date_column_indices or []

        # 3. Сортиране
        sort_sql = ""
        if sort_by:
            sort_sql = self._normalize_order_by(sort_by, safe_table, num_idx, date_idx)
            
        # CTE Logic for Subtotal Filtering
        cte_sql = ""
        main_from = f'"{safe_table}"'
        
        if subtotal_filters and active_groups:
            # Асинхронно създаване на индекси за групите
            self._create_index_async(table_name, active_groups)
            
            group_by_cols = ", ".join([f'"{c.replace("\"", "\"\"")}"' for c in active_groups])
            having_clauses = []
            for sf in subtotal_filters:
                op_map = {
                    'subtotal_gt': '>',
                    'subtotal_lt': '<',
                    'subtotal_gte': '>=',
                    'subtotal_lte': '<=',
                    'subtotal_eq': '=',
                    'subtotal_neq': '!='
                }
                op = op_map.get(sf['condition'], '>')
                having_clauses.append(f'SUM(COALESCE(CAST("{sf["measure"].replace("\"", "\"\"")}" AS REAL), 0)) {op} {sf["value"]}')
            
            having_sql = " HAVING " + " AND ".join(having_clauses)
            
            cte_sql = f"""
            WITH grouped_filter AS (
                SELECT {group_by_cols}
                FROM "{safe_table}"
                {where_sql}
                GROUP BY {group_by_cols}
                {having_sql}
            )
            """
            join_cond = " AND ".join([f's."{c.replace("\"", "\"\"")}" = g."{c.replace("\"", "\"\"")}"' for c in active_groups])
            main_from = f'"{safe_table}" s JOIN grouped_filter g ON {join_cond}'
            
            # Use prefixing for main query WHERE clauses
            where_clauses_prefixed = self._build_where_clauses(all_filters, search_value, text_columns, active_groups, table_name, None, prefix='s')
            where_sql_prefixed = ""
            if where_clauses_prefixed:
                where_sql_prefixed = " WHERE " + " AND ".join(where_clauses_prefixed)
            
            count_query = f'{cte_sql} SELECT COUNT(*) FROM {main_from} {where_sql_prefixed}'
            sort_sql_prefixed = self._normalize_order_by(sort_by, safe_table, num_idx, date_idx, table_alias='s') if sort_by else ""
            main_query = f'{cte_sql} SELECT s.* FROM {main_from} {where_sql_prefixed} {sort_sql_prefixed} LIMIT {limit} OFFSET {offset}'
        else:
            # Заявка за броене (преди LIMIT)
            count_query = f'SELECT COUNT(*) FROM "{safe_table}"' + where_sql
            # Основна заявка с LIMIT и OFFSET
            main_query = f'SELECT * FROM "{safe_table}"' + where_sql + sort_sql + f" LIMIT {limit} OFFSET {offset}"
        
        print(f"DEBUG Main SQL: {main_query}")
            
        return main_query, count_query

    def execute_query(self, query: str) -> pd.DataFrame:
        print(f"DEBUG SQL: {query}")
        conn = self._get_connection()
        try:
            df = pd.read_sql_query(query, conn)
        finally:
            conn.close()
        return df

    def get_count(self, query: str) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            count = cursor.fetchone()[0]
        finally:
            conn.close()
        return count

    def get_unique_values(
        self,
        table_name: str,
        column_name: str,
        filters: dict = None,
        search_value: str = None,
        text_columns: list = None,
        limit: int = 10000,
        numeric_column_indices: list = None,
        date_column_indices: list = None,
    ):
        """Връща уникални стойности за дадена колона, съобразени с активните филтри в другите колони (Каскадно)"""
        
        # 1. Prepare filters for common builder, but IGNORE current column
        all_filters = (filters or {}).copy()
        
        # Check for global ignore flag (used by Advanced Search/Select2)
        ignore_all = all_filters.pop('ignore_all_filters', 'false') == 'true'
        if ignore_all:
            # Clear all filters except system ones if we want a clean global search
            all_filters = {}

        # Helper to recursively filter out a specific column from SearchBuilder criteria
        def filter_out_col_sb(criteria, col_name):
            new_criteria = []
            for c in criteria:
                if 'logic' in c:
                    sub = filter_out_col_sb(c['criteria'], col_name)
                    if sub: new_criteria.append({'logic': c['logic'], 'criteria': sub})
                elif c.get('data') != col_name:
                    new_criteria.append(c)
            return new_criteria

        if 'sb' in all_filters:
            try:
                sb_state = all_filters['sb']
                if isinstance(sb_state, str):
                    sb = json.loads(sb_state)
                else:
                    sb = sb_state
                
                if sb and 'criteria' in sb:
                    sb['criteria'] = filter_out_col_sb(sb['criteria'], column_name)
                    all_filters['sb'] = sb
            except: pass

        # Remove legacy filters for current column
        for k in list(all_filters.keys()):
            if k == column_name or k.startswith(f"{column_name}_"):
                all_filters.pop(k)

        where_clauses = self._build_where_clauses(all_filters, search_value, text_columns)
        
        where_sql = ""
        if where_clauses:
            where_sql = " WHERE " + " AND ".join(where_clauses)
            
        # Safely quote table and column names
        safe_table = table_name.replace('"', '""')
        safe_col = column_name.replace('"', '""')

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA table_info("{safe_table}")')
            headers = [row[1] for row in cursor.fetchall()]
        finally:
            conn.close()

        num_idx = numeric_column_indices or []
        date_idx = date_column_indices or []
        if column_name in headers:
            cidx = headers.index(column_name)
            if cidx in num_idx:
                order_expr = f'CAST("{safe_col}" AS REAL)'
            elif cidx in date_idx:
                order_expr = f'"{safe_col}"'  # INTEGER сортира директно
            else:
                order_expr = f'LOWER("{safe_col}")'
        else:
            order_expr = f'"{safe_col}"'

        # Лимит до 5000 уникални стойности за DropDown филтрите
        query = f'SELECT DISTINCT "{safe_col}" FROM "{safe_table}"' + where_sql + f" ORDER BY {order_expr} LIMIT 5000"
        
        print(f"DEBUG Unique SQL for {column_name}: {query}")
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            values = [row[0] for row in cursor.fetchall() if row[0] is not None and str(row[0]).strip() != ""]
        finally:
            conn.close()
        return values

    def get_column_stats(self, table_name: str, numeric_columns: list, date_columns: list, 
                         filters: dict = None, search_value: str = None, text_columns: list = None):
        """Изчислява описателна статистика директно от SQLite базата с поддръжка на филтри"""
        stats_dict = {}
        
        # Генерираме WHERE клаузата за текущите филтри
        where_clauses = self._build_where_clauses(filters, search_value, text_columns)
        
        where_sql = ""
        if where_clauses:
            where_sql = " WHERE " + " AND ".join(where_clauses)

        print(f"DEBUG Stats Where SQL: {where_sql}")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Safely quote table name
            safe_table = table_name.replace('"', '""')
            
            cursor.execute(f'SELECT * FROM "{safe_table}" LIMIT 0')
            headers = [desc[0] for desc in cursor.description]
            
            for i, col in enumerate(headers):
                # Safely quote column name
                safe_col = col.replace('"', '""')
                
                # 1. Общи статистики (винаги върху цялата база)
                cursor.execute(f'SELECT COUNT(*), COUNT(DISTINCT "{safe_col}"), SUM(CASE WHEN "{safe_col}" IS NULL OR "{safe_col}" = "" THEN 1 ELSE 0 END) FROM "{safe_table}"')
                total, unique, empty = cursor.fetchone()
                
                # 2. Филтрирани статистики (върху текущия избор)
                cursor.execute(f'SELECT COUNT(*), COUNT(DISTINCT "{safe_col}"), SUM(CASE WHEN "{safe_col}" IS NULL OR "{safe_col}" = "" THEN 1 ELSE 0 END) FROM "{safe_table}" {where_sql}')
                f_total, f_unique, f_empty = cursor.fetchone()

                col_stats = {
                    "total": total,
                    "unique": unique,
                    "empty": empty,
                    "f_total": f_total,
                    "f_unique": f_unique,
                    "f_empty": f_empty,
                    "type": "text"
                }
                
                # 3. Специфични статистики
                if i in numeric_columns:
                    # Global
                    cursor.execute(f'SELECT MAX(CAST("{safe_col}" AS REAL)), MIN(CAST("{safe_col}" AS REAL)), AVG(CAST("{safe_col}" AS REAL)) FROM "{safe_table}"')
                    max_val, min_val, avg_val = cursor.fetchone()
                    # Filtered
                    filtered_num_query = (
                        f'SELECT MAX(CAST("{safe_col}" AS REAL)), MIN(CAST("{safe_col}" AS REAL)), AVG(CAST("{safe_col}" AS REAL)), '
                        f'SUM(CASE WHEN CAST("{safe_col}" AS REAL) > 0 THEN 1 ELSE 0 END), '
                        f'SUM(CASE WHEN CAST("{safe_col}" AS REAL) < 0 THEN 1 ELSE 0 END), '
                        f'SUM(CASE WHEN CAST("{safe_col}" AS REAL) = 0 THEN 1 ELSE 0 END) '
                        f'FROM "{safe_table}" {where_sql}'
                    )
                    cursor.execute(filtered_num_query)
                    f_max, f_min, f_avg, f_pos, f_neg, f_zero = cursor.fetchone()

                    col_stats.update({
                        "type": "numeric",
                        "max": max_val,
                        "min": min_val,
                        "avg": avg_val,
                        "f_max": f_max,
                        "f_min": f_min,
                        "f_avg": f_avg,
                        "f_positives": f_pos or 0,
                        "f_negatives": f_neg or 0,
                        "f_zeros": f_zero or 0
                    })
                elif i in date_columns:
                    # Global
                    cursor.execute(f'SELECT MAX("{safe_col}"), MIN("{safe_col}") FROM "{safe_table}" WHERE "{safe_col}" IS NOT NULL AND "{safe_col}" != ""')
                    max_val, min_val = cursor.fetchone()
                    # Filtered
                    date_where = where_sql + (" AND " if where_clauses else " WHERE ") + f'"{safe_col}" IS NOT NULL AND "{safe_col}" != ""'
                    cursor.execute(f'SELECT MAX("{safe_col}"), MIN("{safe_col}") FROM "{safe_table}" {date_where}')
                    f_max, f_min = cursor.fetchone()

                    col_stats.update({
                        "type": "date",
                        "max": max_val,
                        "min": min_val,
                        "f_max": f_max,
                        "f_min": f_min
                    })
                
                # 4. Честоти (TOP 1000) с разграничаване на допустими/недопустими
                filter_condition = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                freq_query = (
                    f'SELECT "{safe_col}", COUNT(*) as total_cnt, '
                    f'SUM(CASE WHEN {filter_condition} THEN 1 ELSE 0 END) as filtered_cnt '
                    f'FROM "{safe_table}" '
                    f'GROUP BY "{safe_col}" '
                    f'ORDER BY (CASE WHEN SUM(CASE WHEN {filter_condition} THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 0 END) DESC, total_cnt DESC '
                    f'LIMIT 1000'
                )
                cursor.execute(freq_query)
                
                col_stats["frequencies_v2"] = [
                    {
                        "val": str(row[0]) if row[0] is not None else "", 
                        "count": int(row[1]), 
                        "filtered_count": int(row[2]),
                        "allowed": row[2] > 0
                    }
                    for row in cursor.fetchall()
                ]
                
                stats_dict[col] = col_stats
                
        finally:
            conn.close()
            
        return stats_dict

    def get_group_subtotals(
        self,
        table_name: str,
        group_columns: list,
        sum_column: str,
        filters: dict = None,
        search_value: str = None,
        text_columns: list = None,
    ) -> dict:
        """Връща междинни суми по групи (за динамичен режим и пълни суми извън pagination)."""
        if not group_columns or not sum_column:
            return {}

        all_filters = (filters or {}).copy()
        # Премахваме системните ключове, които не участват в WHERE логиката.
        # Ако останат, се третират като колони и чупят SQL-а в динамичен режим.
        for k in (
            "active_groups",
            "active_group_indices",
            "subtotal_ui_col",
            "subtotal_ui_col_idx",
            "subtotal_ui_op",
            "subtotal_ui_value",
            "numeric_columns",
            "date_columns",
            "text_columns",
            "limit",
            "offset",
            "sort_by",
            "search",
            "sb",
        ):
            all_filters.pop(k, None)

        # SearchBuilder state се подава отделно, за да е еднаква филтрацията с main query.
        if filters and filters.get("sb"):
            all_filters["sb"] = filters.get("sb")

        where_clauses = self._build_where_clauses(
            all_filters,
            search_value,
            text_columns,
            active_groups=group_columns,
            table_name=table_name,
            subtotal_filters=[],
        )
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        safe_table = table_name.replace('"', '""')
        safe_sum = sum_column.replace('"', '""')
        safe_groups = [g.replace('"', '""') for g in group_columns]
        group_sql = ", ".join([f'"{g}"' for g in safe_groups])

        query = (
            f'SELECT {group_sql}, SUM(COALESCE(CAST("{safe_sum}" AS REAL), 0)) as subtotal '
            f'FROM "{safe_table}" {where_sql} GROUP BY {group_sql}'
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            result = {}
            for row in cursor.fetchall():
                key_parts = [str(v if v is not None else "") for v in row[:-1]]
                val = float(row[-1] or 0)
                # Добавяме сума за всяко ниво на групиране: A, A|B, A|B|C...
                run = []
                for part in key_parts:
                    run.append(part)
                    key = "|".join(run)
                    result[key] = float(result.get(key, 0.0)) + val
            return result
        finally:
            conn.close()
