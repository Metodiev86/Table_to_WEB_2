from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
import os
import pandas as pd
from pathlib import Path
from query_manager import QueryManager
from loader import DataLoader
from generator import DataTableGenerator
from db_config import MSSQL_CONN_STR
from DataFrame_Handler import DataTransformer
from collections import defaultdict
import datetime
import socket
import threading
import sys
import json
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw
from report_model import Report
from loader import DataLoader as SqlDataLoader
from parameter_loader import load_parameter_values, has_dynamic_source

app = Flask(__name__)

REPORTS_DIR = Path(__file__).parent / "output"
PRIVATE_REPORTS_DIR = Path(__file__).parent / "private_output"
SECRET_REPORTS_DIR = Path(__file__).parent / "secret_output"
PRIVATE_REPORTS_DIR.mkdir(exist_ok=True)
SECRET_REPORTS_DIR.mkdir(exist_ok=True)
DB_DIR = Path(__file__).parent / "databases"
METADATA_DIR = Path(__file__).parent / "metadata"
SQL_QUERIES_DIR = Path(__file__).parent / "sql_queries"
REPORTS_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)
SQL_QUERIES_DIR.mkdir(exist_ok=True)

# Ключове за достъп по ниво
ACCESS_KEYS = {
    "private": "12345",
    "secret":  "99999",  # <-- сменете с реален ключ
}

# Този речник може да остане като fallback или за фиксирани категории
REPORT_CATEGORIES = {
    "Оферти": "Справки",
    "Касова Книга_Архив": "Разплащания",
    "Касова Книга_Днес": "Разплащания",
    "Клиенти_с_просрочия": "Просрочия",
    "operations_log": "Операции",
    "new_report": "Финанси"   # ➜ нова категория
}

# --- System Tray Functions ---
def get_ip_addresses():
    # Намиране на локалните IP адреси за показване в Tooltip (Hint)
    ips = []
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        ips.append(local_ip)
        
        # Опитваме се да намерим всички мрежови IP-та (IPv4)
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if "." in ip and ip not in ips:
                ips.append(ip)
    except:
        pass
    
    msg = "Сървърът работи на:\n"
    if not ips:
        msg += "localhost:5010"
    else:
        msg += "\n".join([f"http://{ip}:5010" for ip in ips])
    return msg

def create_tray_image():
    # Създаване на жълто-оранжев квадратен индикатор
    image = Image.new('RGB', (64, 64), color=(255, 165, 0)) # Оранжева рамка
    draw = ImageDraw.Draw(image)
    # По-светъл жълто-оранжев център за по-добър вид
    draw.rectangle((12, 12, 52, 52), fill=(255, 215, 0)) # Златисто жълто
    return image

def restart_server(icon):
    # Рестартиране на целия скрипт
    icon.stop()
    python = sys.executable
    os.execv(python, [python] + sys.argv)

def exit_action(icon):
    # Прекъсване на процеса
    icon.stop()
    os._exit(0)

def run_tray():
    # Стартиране на иконата в системния трей
    icon = Icon(
        "FlaskServer",
        create_tray_image(),
        get_ip_addresses(),
        menu=Menu(
            MenuItem("Restart", restart_server),
            MenuItem("Exit", exit_action)
        )
    )
    icon.run()
# --- End of Tray Functions ---

def get_report_category(report_name):
    metadata_file = METADATA_DIR / (report_name + ".json")
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("category", "Други")
        except:
            pass
    return REPORT_CATEGORIES.get(report_name, "Други")

CATEGORY_ORDER = [
    "Справки",
    "Номенклатури",
    "Просрочия",
    "Разплащания",
    "Задължения",
    "Транспорт",
    "Финанси",
    "Операции",
    "Други"
]

CATEGORY_META = {
    "Справки": {"order": 1, "icon": "📊"},
    "Просрочия": {"order": 2, "icon": "📉"},
    "Разплащания": {"order": 3, "icon": "💰"},
    "Операции": {"order": 4, "icon": "⚙️"},
    "Задължения": {"order": 5, "icon": "💳"},
    "Транспорт": {"order": 6, "icon": "🚚"},
    "Други": {"order": 7, "icon": "📂"}
}

def get_access_level() -> str:
    """Връща нивото на достъп на заявката: 'secret' > 'private' > 'public'."""
    # Проверяваме първо от GET параметри
    key = request.args.get("key")
    # Ако няма, проверяваме от POST JSON тяло
    if not key and request.is_json:
        data = request.get_json(silent=True) or {}
        key = data.get("key")
    if key == ACCESS_KEYS["secret"]:
        return "secret"
    if key == ACCESS_KEYS["private"]:
        return "private"
    return "public"

def get_report_access(report_name: str) -> str:
    """Връща нивото на достъп, необходимо за даден отчет."""
    if (SECRET_REPORTS_DIR / (report_name + ".html")).exists():
        return "secret"
    if (PRIVATE_REPORTS_DIR / (report_name + ".html")).exists():
        return "private"
    return "public"

def _check_report_access(report_name: str):
    """Проверка за достъп; връща (None, error_response) или (report_name, None)."""
    _levels = ["public", "private", "secret"]
    if _levels.index(get_access_level()) < _levels.index(get_report_access(report_name)):
        return None, (jsonify({"error": "Unauthorized"}), 403)
    return report_name, None


def _execute_report_query(report_name: str, raw_parameters: dict | None = None):
    """Изпълнява параметризирана или обикновена SQL справка и връща DataFrame + метаданни."""
    report = Report.load(report_name)
    if not report or not report.sql:
        raise FileNotFoundError(f"SQL query file not found for: {report_name}")

    sql_file = SQL_QUERIES_DIR / (report_name + ".sql")
    loader = SqlDataLoader()
    handler = DataTransformer().handler
    validated_params = {}

    if report.has_parameters:
        validated_params = report.validate_parameters(raw_parameters)
        df = loader.load_sql_with_params(
            str(sql_file),
            connection_string=MSSQL_CONN_STR,
            params=validated_params,
        )
    else:
        df = loader.load(str(sql_file), connection_string=MSSQL_CONN_STR)

    df, date_columns, column_metadata = handler.detect_date_columns(df)
    numeric_columns, _ = handler.detect_numeric_columns(df, date_columns)

    db_path = DB_DIR / (report_name + ".sqlite")
    if db_path.exists():
        from sqlalchemy import create_engine
        sqlite_engine = create_engine(f"sqlite:///{db_path}")
        df.to_sql(report_name, sqlite_engine, if_exists="replace", index=False)

    descriptive_stats = handler.calculate_descriptive_stats(df, date_columns, numeric_columns)

    return {
        "df": df,
        "date_columns": date_columns,
        "numeric_columns": numeric_columns,
        "column_metadata": column_metadata,
        "descriptive_stats": descriptive_stats,
        "validated_params": validated_params if report.has_parameters else {},
    }


@app.route('/api/report', methods=['POST'])
def api_execute_report():
    """Изпълнява справка с параметри (POST JSON)."""
    try:
        body = request.get_json(silent=True) or {}
        report_name = body.get("report")
        if not report_name:
            return jsonify({"error": "Missing 'report' field"}), 400

        _, err = _check_report_access(report_name)
        if err:
            return err

        report = Report.load(report_name)
        if not report:
            return jsonify({"error": f"Report not found: {report_name}"}), 404

        raw_parameters = body.get("parameters")
        if report.has_parameters:
            if raw_parameters is None:
                raw_parameters = report.default_parameters()
        elif raw_parameters:
            return jsonify({"error": "This report does not accept parameters"}), 400

        result = _execute_report_query(report_name, raw_parameters)
        df = result["df"]

        return jsonify({
            "data": df.fillna("").values.tolist(),
            "total": len(df),
            "descriptive_stats": {str(k): v for k, v in result["descriptive_stats"].items()},
            "parameters": result["validated_params"],
            "date_columns": result["date_columns"],
            "numeric_columns": result["numeric_columns"],
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        import traceback
        print(f"ERROR in api_execute_report: {traceback.format_exc()}")
        return jsonify({"error": str(exc)}), 500


def _collect_reports_from_dir(directory: Path, access_level: str) -> list:
    """Помощна функция – събира отчети от папка и им закача ниво на достъп."""
    result = []
    if not directory.exists():
        return result
    for file in directory.glob("*.html"):
        modified_date = datetime.datetime.fromtimestamp(
            file.stat().st_mtime
        ).strftime("%d.%m.%Y %H:%M")
        result.append({
            "name": file.stem,
            "filename": file.name,
            "has_db": (DB_DIR / (file.stem + ".sqlite")).exists(),
            "is_live": (SQL_QUERIES_DIR / (file.stem + ".sql")).exists(),
            "access": access_level,
            "is_private": access_level != "public",   # съвместимост с template
            "is_secret": access_level == "secret",
            "category": get_report_category(file.stem),
            "created": modified_date,
        })
    return result

def group_and_order_reports(reports):
    grouped_reports = defaultdict(list)

    for r in reports:
        grouped_reports[r["category"]].append(r)

    ordered_groups = []

    # първо по зададения ред
    for cat in CATEGORY_ORDER:
        if cat in grouped_reports:
            ordered_groups.append((cat, grouped_reports[cat]))

    # после останалите
    for cat in grouped_reports:
        if cat not in CATEGORY_ORDER:
            ordered_groups.append((cat, grouped_reports[cat]))

    return ordered_groups

@app.route('/')
def render_index():
    """Публичен изглед – само отчети от output/."""
    reports = _collect_reports_from_dir(REPORTS_DIR, "public")
    ordered_groups = group_and_order_reports(reports)
    return render_template('index_1.html', grouped_reports=ordered_groups,
                           access_level="public", CATEGORY_META=CATEGORY_META)

@app.route('/internal')
def render_internal():
    """Private изглед – public + private отчети (изисква private ключ)."""
    if get_access_level() not in ("private", "secret"):
        return "Forbidden", 403

    reports = (
        _collect_reports_from_dir(REPORTS_DIR, "public") +
        _collect_reports_from_dir(PRIVATE_REPORTS_DIR, "private")
    )
    ordered_groups = group_and_order_reports(reports)
    return render_template('index_1.html', grouped_reports=ordered_groups,
                           access_level="private", CATEGORY_META=CATEGORY_META)

@app.route('/secret')
def render_secret():
    """Secret изглед – public + private + secret отчети (изисква secret ключ)."""
    if get_access_level() != "secret":
        return "Forbidden", 403

    reports = (
        _collect_reports_from_dir(REPORTS_DIR, "public") +
        _collect_reports_from_dir(PRIVATE_REPORTS_DIR, "private") +
        _collect_reports_from_dir(SECRET_REPORTS_DIR, "secret")
    )
    ordered_groups = group_and_order_reports(reports)
    return render_template('index_1.html', grouped_reports=ordered_groups,
                           access_level="secret", CATEGORY_META=CATEGORY_META)

@app.route('/report/live/<report_name>')
def serve_live_report(report_name):
    # Проверка за оторизация спрямо нивото на отчета
    required = get_report_access(report_name)
    user_level = get_access_level()
    _levels = ["public", "private", "secret"]
    if _levels.index(user_level) < _levels.index(required):
        return "Forbidden", 403

    # Път към SQL заявката
    sql_file = SQL_QUERIES_DIR / (report_name + ".sql")
    if not sql_file.exists():
        return f"SQL query file not found for: {report_name}", 404

    try:
        report = Report.load(report_name)
        
        if report and report.has_parameters:
            # За параметризирани справки изпълняваме заявката веднъж с default параметри, за да получим заглавията на колоните
            print(f"DEBUG: Parameterized report {report_name}, generating HTML with default params")
            
            # Изпълняваме заявката с default параметри
            result = _execute_report_query(report_name, report.default_parameters())
            df = result["df"]
            
            # Търсим къде е HTML файла (публичен или частен)
            html_file = REPORTS_DIR / (report_name + ".html")
            if not html_file.exists():
                html_file = PRIVATE_REPORTS_DIR / (report_name + ".html")
            if not html_file.exists():
                html_file = SECRET_REPORTS_DIR / (report_name + ".html")
            if not html_file.exists():
                html_file = REPORTS_DIR / (report_name + ".html")  # дефолт
                
            # Обновяване на HTML файла чрез Генератора с реалният DataFrame (за да имаме заглавия)
            generator = DataTableGenerator("Template/template_Table_to_HTML.html")
            generator.generate_dynamic_template(str(sql_file), df, str(html_file), report_name=report_name, is_dynamic_override=False)
            
            # Обновяваме mtime за всеки случай
            html_file.touch()
        
        else:
            # Изпълнение на заявката през DataLoader за не-параметризирани справки
            loader = DataLoader()
            print(f"DEBUG: Executing live query for {report_name} from {sql_file}")
            df = loader.load(str(sql_file), connection_string=MSSQL_CONN_STR)
            print(f"DEBUG: Query returned {len(df)} rows")
            
            # Обновяване на SQLite базата данни ако съществува
            db_path = DB_DIR / (report_name + ".sqlite")
            is_dynamic = db_path.exists()
            
            if is_dynamic:
                from sqlalchemy import create_engine
                sqlite_engine = create_engine(f"sqlite:///{db_path}")
                df.to_sql(report_name, sqlite_engine, if_exists='replace', index=False)
                print(f"DEBUG: SQLite database updated at {db_path}")
            
            # Търсим къде е HTML файла (публичен или частен)
            html_file = REPORTS_DIR / (report_name + ".html")
            if not html_file.exists():
                html_file = PRIVATE_REPORTS_DIR / (report_name + ".html")
            if not html_file.exists():
                html_file = SECRET_REPORTS_DIR / (report_name + ".html")
            if not html_file.exists():
                html_file = REPORTS_DIR / (report_name + ".html")  # дефолт
            
            # Обновяване на HTML файла чрез Генератора
            generator = DataTableGenerator("Template/template_Table_to_HTML.html")
            
            if is_dynamic:
                print(f"DEBUG: Regenerating dynamic shell for {report_name}")
                generator.generate_dynamic_template(str(sql_file), df, str(html_file), report_name=report_name)
            else:
                print(f"DEBUG: Regenerating static report for {report_name}")
                generator.generate_static_report(str(sql_file), df, str(html_file))
                
            # Обновяваме mtime за всеки случай
            html_file.touch()
        
        # Пренасочване към стандартния маршрут за отчети
        redirect_args = request.args.to_dict()
        return redirect(url_for('serve_report', filename=report_name + ".html", **redirect_args))
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR in serve_live_report: {error_details}")
        return f"Error executing live report: {str(e)}", 500

@app.route('/report/<filename>')
def serve_report(filename):
    """Сервира HTML файл спрямо нивото на достъп."""
    _levels = ["public", "private", "secret"]
    user_level = get_access_level()
    stem = Path(filename).stem

    dir_map = [
        (REPORTS_DIR,        "public"),
        (PRIVATE_REPORTS_DIR, "private"),
        (SECRET_REPORTS_DIR,  "secret"),
    ]

    for directory, required in dir_map:
        if (directory / filename).exists():
            if _levels.index(user_level) < _levels.index(required):
                return "Forbidden", 403
            return send_from_directory(directory, filename)

    return "Report not found", 404

@app.route('/api/report/<report_name>/parameters')
def api_get_report_parameters(report_name):
    """Връща актуалните дефиниции на параметрите за дадена справка (с query/source полетата).
    Полезно когато HTML файлът е бил генериран преди промени в metadata JSON-а.
    """
    try:
        _, err = _check_report_access(report_name)
        if err:
            return err

        report = Report.load(report_name)
        if not report:
            return jsonify({"error": "Справката не е намерена"}), 404

        return jsonify({
            "title": report.title,
            "category": report.category,
            "parameters": report.parameter_definitions(),
        })
    except Exception as exc:
        import traceback
        print(f"ERROR in api_get_report_parameters: {traceback.format_exc()}")
        return jsonify({"error": "Грешка при извличане на параметри на справката"}), 500


@app.route('/api/report/parameter-values', methods=['POST'])
def api_load_parameter_values():
    """Изпълнява SQL заявка за стойности на параметър и връща JSON резултат.

    Тяло на заявката:
    {
        "report": "ReportName",       // нужно за оторизация и context
        "param": { ... },              // дефиниция на параметъра (с 'query' или 'source')
        "parameters": { ... }          // опционално – вече избрани стойности за bind (:warehouse)
        "key": "...",                  // опционално – access key за oторизация
    }

    Връща:
      за type == "select": [ {"value": .., "label": ..}, ... ]
      за останалите:        { "value": ... }
    """
    try:
        body = request.get_json(silent=True) or {}
        param_def = body.get("param")
        if not isinstance(param_def, dict):
            return jsonify({"error": "Missing 'param' definition in request body"}), 400

        report_name = body.get("report")
        if report_name:
            _, err = _check_report_access(report_name)
            if err:
                return err

        if not has_dynamic_source(param_def):
            if param_def.get("type") == "select":
                return jsonify(param_def.get("options") or [])
            return jsonify({"value": param_def.get("default")})

        bind_params = body.get("parameters") or {}

        result = load_parameter_values(param_def, bind_params=bind_params)

        if result.is_select_options:
            return jsonify(result.data)
        return jsonify(result.data)

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        import traceback
        print(f"ERROR in api_load_parameter_values: {traceback.format_exc()}")
        return jsonify({"error": "Грешка при зареждане на стойностите за параметъра."}), 500


@app.route('/api/filter/<report_name>')
def api_filter_data(report_name):
    _levels = ["public", "private", "secret"]
    if _levels.index(get_access_level()) < _levels.index(get_report_access(report_name)):
        return jsonify({"error": "Unauthorized"}), 403

    # Приема AJAX заявки за филтриране със сървърна поддръжка
    db_path = DB_DIR / (report_name + ".sqlite")
    if not db_path.exists():
        return jsonify({"error": f"Database not found: {db_path}"}), 404
    
    main_query = None
    count_query = None
    try:
        args = request.args.to_dict()
        limit = int(args.pop('limit', 1000))
        offset = int(args.pop('offset', 0))
        sort_by = args.pop('sort_by', None)
        search_value = args.pop('search', None)
        sb_state = args.pop('sb', None) # Get SearchBuilder state
        numeric_cols = args.pop('numeric_columns', "").split(",")
        numeric_cols = [int(i) for i in numeric_cols if i != ""]
        date_cols = args.pop('date_columns', "").split(",")
        date_cols = [int(i) for i in date_cols if i != ""]
        # Текстови колони за глобално търсене
        text_columns = args.pop('text_columns', "").split(",")
        if text_columns == [""]: text_columns = []
        
        qm = QueryManager(str(db_path))
        main_query, count_query = qm.build_dynamic_query(
            report_name, 
            filters=args, 
            sort_by=sort_by, 
            search_value=search_value, 
            text_columns=text_columns,
            limit=limit, 
            offset=offset,
            sb_state=sb_state,
            numeric_column_indices=numeric_cols,
            date_column_indices=date_cols
        )
        
        df = qm.execute_query(main_query)
        total_records = qm.get_count(count_query)
        
        group_subtotals = {}
        active_groups_raw = args.get('active_groups', '')
        active_group_indices_raw = args.get('active_group_indices', '')
        subtotal_ui_col = args.get('subtotal_ui_col', '')
        subtotal_ui_col_idx_raw = args.get('subtotal_ui_col_idx', '')
        if (active_groups_raw or active_group_indices_raw) and (subtotal_ui_col or subtotal_ui_col_idx_raw):
            headers = qm.get_table_headers(report_name)
            group_cols = []
            if active_group_indices_raw:
                try:
                    idx_list = [int(x) for x in active_group_indices_raw.split(',') if x.strip() != ""]
                    group_cols = [headers[i] for i in idx_list if 0 <= i < len(headers)]
                except Exception:
                    group_cols = []
            if not group_cols and active_groups_raw:
                group_cols = [c for c in active_groups_raw.split('|') if c]

            sum_col = subtotal_ui_col
            if subtotal_ui_col_idx_raw:
                try:
                    i = int(subtotal_ui_col_idx_raw)
                    if 0 <= i < len(headers):
                        sum_col = headers[i]
                except Exception:
                    pass
            if group_cols:
                try:
                    subtotal_filters = args.copy()
                    if sb_state:
                        subtotal_filters['sb'] = sb_state
                    group_subtotals = qm.get_group_subtotals(
                        report_name,
                        group_cols,
                        sum_col,
                        filters=subtotal_filters,
                        search_value=search_value,
                        text_columns=text_columns
                    )
                except Exception as subtotal_err:
                    print(f"WARNING in group subtotals: {subtotal_err}")
                    group_subtotals = {}
        
        return jsonify({
            "data": df.fillna("").values.tolist(),
            "total": total_records,
            "group_subtotals": group_subtotals
        })
    except Exception as e:
        print(f"ERROR in api_filter_data: {str(e)}")
        if main_query:
            print(f"ERROR main_query: {main_query}")
        if count_query:
            print(f"ERROR count_query: {count_query}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/unique/<report_name>/<column_name>')
def api_get_unique_values(report_name, column_name):

    _levels = ["public", "private", "secret"]
    if _levels.index(get_access_level()) < _levels.index(get_report_access(report_name)):
        return jsonify({"error": "Unauthorized"}), 403

    # Връща уникални стойности за каскадни филтри
    db_path = DB_DIR / (report_name + ".sqlite")
    if not db_path.exists():
        return jsonify({"error": f"Database not found: {db_path}"}), 404
        
    try:
        args = request.args.to_dict()
        search_value = args.pop('search', None)
        text_columns = args.pop('text_columns', "").split(",")
        if text_columns == [""]: text_columns = []
        
        qm = QueryManager(str(db_path))
        values = qm.get_unique_values(report_name, column_name, filters=args, search_value=search_value, text_columns=text_columns)
        
        return jsonify(values)
    except Exception as e:
        print(f"ERROR in api_get_unique_values: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats/<report_name>')
def api_get_stats(report_name):

    _levels = ["public", "private", "secret"]
    if _levels.index(get_access_level()) < _levels.index(get_report_access(report_name)):
        return jsonify({"error": "Unauthorized"}), 403

    # Връща описателна статистика за всички колони с поддръжка на филтри
    db_path = DB_DIR / (report_name + ".sqlite")
    if not db_path.exists():
        return jsonify({"error": f"Database not found: {db_path}"}), 404
        
    try:
        args = request.args.to_dict()
        numeric_cols = args.pop('numeric_columns', "").split(",")
        numeric_cols = [int(i) for i in numeric_cols if i != ""]
        
        date_cols = args.pop('date_columns', "").split(",")
        date_cols = [int(i) for i in date_cols if i != ""]

        search_value = args.pop('search', None)
        text_columns = args.pop('text_columns', "").split(",")
        if text_columns == [""]: text_columns = []
        
        qm = QueryManager(str(db_path))
        stats = qm.get_column_stats(
            report_name, 
            numeric_cols, 
            date_cols, 
            filters=args, 
            search_value=search_value, 
            text_columns=text_columns
        )
        
        return jsonify(stats)
    except Exception as e:
        print(f"ERROR in api_get_stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Стартираме Flask в отделна нишка (Thread)
    # Задаваме use_reloader=False, за да не се рестартира трей иконата при промяна на кода
    threading.Thread(target=lambda: app.run(host="0.0.0.0", debug=False, port=5010, use_reloader=False), daemon=True).start()
    
    # Стартираме иконата в системния трей (blocking)
    run_tray()
