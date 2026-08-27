# Table_to_WEB — BI Reporting Platform

**Web-базирана BI система за генериране и обслужване на интерактивни справки от произволни източници на данни (Excel, CSV, JSON, Parquet, XML, SQL заявки) с многостепенен контрол на достъпа, live обновяване и клиентско/сървърно филтриране на големи обеми данни.**

Системата се състои от два основни режима на работа:

1. **Пакетна генерация на справки** (`report_template.pyw`) — превръща файл с данни (или SQL заявка) в самостоятелен, стилизиран HTML отчет с вградена таблица (DataTables), готов за преглед без сървър.
2. **Уеб портал** (`Flask_Report.pyw`) — Flask приложение, което сервира генерираните справки, поддържа "live" (динамично обновявани при отваряне) справки директно от SQL Server, и предоставя AJAX API за сървърно филтриране, сортиране, статистика и междинни суми върху големи таблици чрез локална SQLite база на справка.

---

## Съдържание

- [Архитектура на системата](#архитектура-на-системата)
- [Структура на файловете](#структура-на-файловете)
- [Как работи: път на данните](#как-работи-път-на-данните)
- [Нива на достъп](#нива-на-достъп)
- [Модул по модул](#модул-по-модул)
  - [`Config.py` / `db_config.py`](#configpy--db_configpy)
  - [`Load_from_External_File.py`](#load_from_external_filepy)
  - [`loader.py`](#loaderpy)
  - [`DataFrame_Handler.py`](#dataframe_handlerpy)
  - [`sqlite_injector.py`](#sqlite_injectorpy)
  - [`query_manager.py`](#query_managerpy)
  - [`parameter_loader.py` / `parameter_resolver.py`](#parameter_loaderpy--parameter_resolverpy)
  - [`report_template.pyw`](#report_templatepyw)
  - [`parameter_editor.pyw`](#parameter_editorpyw)
  - [`Flask_Report.pyw`](#flask_reportpyw)
  - [`template_Table_to_HTML.html`](#template_table_to_htmlhtml)
- [Формат на JSON метаданните за параметризирани справки](#формат-на-json-метаданните-за-параметризирани-справки)
- [API справочник (Flask)](#api-справочник-flask)
- [Статичен срещу динамичен режим на справка](#статичен-срещу-динамичен-режим-на-справка)
- [Автоматично индексиране в SQLite](#автоматично-индексиране-в-sqlite)
- [Конфигурация и променливи на средата](#конфигурация-и-променливи-на-средата)
- [Инсталация и зависимости](#инсталация-и-зависимости)
- [Стартиране](#стартиране)
- [Липсваща документация (модули извън обхвата на този README)](#липсваща-документация-модули-извън-обхвата-на-този-readme)
- [Известни особености / технически дълг](#известни-особености--технически-дълг)

---

## Архитектура на системата

```
                    ┌──────────────────────────────┐
                    │   Източник на данни           │
                    │ .xlsx .csv .json .parquet     │
                    │ .xml .sql (SQL Server)        │
                    └───────────────┬───────────────┘
                                    │
                     Load_from_External_File.py /
                          loader.py (FileProcessor)
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │   DataFrame_Handler.py        │
                    │  почистване, detect типове,   │
                    │  описателна статистика         │
                    └───────────────┬───────────────┘
                                    │
                     row_count < 10 000 ?
                        ┌───────────┴───────────┐
                       ДА                       НЕ
                        │                        │
                        ▼                        ▼
              Статичен HTML          sqlite_injector.py → report.sqlite
           (данните са вградени         + Динамичен HTML shell
             директно в страницата)   (данните се теглят през AJAX)
                        │                        │
                        └───────────┬────────────┘
                                    ▼
                    template_Table_to_HTML.html
                 (DataTables: филтри, subtotal-и,
                  export Excel/PDF/CSV, статистика)
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │      Flask_Report.pyw          │
                    │  портал + достъп по нива +     │
                    │  AJAX endpoints (query_manager) │
                    └──────────────────────────────┘
```

Две напълно различни "входни точки" произвеждат едно и също: готов HTML файл в `output/` (или `private_output/` / `secret_output/`), който Flask сервира. `report_template.pyw` е за еднократна/пакетна (batch/cron) генерация; `Flask_Report.pyw` допълнително може да **регенерира "на живо"** справка при отваряне (`/report/live/<name>`), директно от SQL Server, без ръчна намеса.

---

## Структура на файловете

| Файл | Роля |
|------|------|
| `Config.py` | Пътища до всички работни директории (output, databases, logs, metadata, queries) — специфични за конкретната машина. |
| `db_config.py` | MSSQL connection strings (StabiDi/Kodima бази) от `DB_USERNAME`/`DB_PASSWORD` env variables. |
| `Load_from_External_File.py` | Прост Tkinter `filedialog` избор на файл с данни. |
| `loader.py` | `FileProcessor`/`DataLoader` — универсално зареждане на файл (или изпълнение на `.sql` файл, вкл. с bind параметри) в `pandas.DataFrame`. |
| `DataFrame_Handler.py` | `DataTransformer`/`DataFrameHandler` — почистване, разпознаване на дати/числа/валути, описателна статистика по колона. |
| `sqlite_injector.py` | `SQLiteInjector` — записва/добавя DataFrame в SQLite база (per-report), с WAL режим, custom SQL функции, автоматични индекси. |
| `query_manager.py` | `QueryManager` — динамично построяване на SQL (филтри, търсене, сортиране, pagination, subtotals, статистика) срещу SQLite базата на справка; управление на автоматични индекси. |
| `parameter_loader.py` | Изпълнява SQL заявки за динамично зареждане на стойности на параметри (dropdown опции / изчислени default-и). |
| `parameter_resolver.py` | Валидация и нормализация на стойности на параметри (`date`, `number`, `checkbox`, `select`), вкл. relative дати (`today-90`). |
| `parameter_editor.pyw` | Desktop (Tkinter) GUI за създаване/редакция на JSON файловете с дефиниции на параметри на справка. |
| `report_template.pyw` | Batch скрипт: файл → почистен DataFrame → статичен/динамичен HTML отчет + метаданни + логове + Windows toast известие. |
| `Flask_Report.pyw` | Flask уеб приложение + системен трей икона: портал, нива на достъп, live регенерация, AJAX API. |
| `template_Table_to_HTML.html` | Jinja/placeholder HTML шаблон в основата на всеки генериран отчет — DataTables 2.2.2 с пълен набор от разширения. |
| `index_1.html` | Jinja темплейт на самия портал (началната страница със справки, групирани по категория). |

> Модулите `generator.py` (класове `HTMLGenerator`/`DataTableGenerator`, попълващи `template_Table_to_HTML.html`) и `report_model.py` (класът `Report`) се използват навсякъде в системата, но не са били част от подадените файлове — вижте [Липсваща документация](#липсваща-документация-модули-извън-обхвата-на-този-readme).

---

## Как работи: път на данните

### 1. Генериране на справка (batch)

```python
from report_template import generate_report
from Config import OUTPUT_DIR_Public
from pathlib import Path

generate_report(
    file_in=Path("data/sales_january.xlsx"),
    file_out=OUTPUT_DIR_Public / "sales_january.html",
    category="Справки",
)
```

Стъпки вътре в `generate_report`:

1. Ако `category` не е подадена — изскача Tkinter диалог (`askstring`), който я изисква (задължително поле).
2. `FileProcessor.load_file(...)` зарежда файла в DataFrame (по разширение).
3. `DataTransformer.clean_data(...)` премахва напълно празните редове.
4. Пише се `metadata/<report_name>.json` с категорията (ползва се от портала за групиране).
5. Ако `len(df) < 10000` → **статичен** HTML (данните се вграждат директно в страницата).
6. Ако `len(df) >= 10000` → данните се записват в `databases/<report_name>.sqlite` (`SQLiteInjector.inject_data`, пълен rebuild) + генерира се **динамичен** HTML shell, който тегли данните през AJAX.
7. Логва се успех/грешка в `logs/success_log.csv` / `logs/error_log.csv`, и излиза Windows toast известие (`winotify`).

### 2. Обслужване през уеб (Flask)

- Портал `/`, `/internal`, `/secret` — показват справките от съответните директории (`output/`, `private_output/`, `secret_output/`), групирани по категория, сортирани по фиксиран приоритетен ред (`CATEGORY_ORDER`).
- Отваряне на конкретна справка → `/report/<filename>` сервира готовия HTML файл (със проверка на нивото на достъп спрямо директорията, в която се намира).
- **Live справки** (тези, за които съществува `.sql` файл в `sql_queries/`) минават през `/report/live/<report_name>`: заявката се изпълнява наново срещу MSSQL (`loader.py` / `_execute_report_query`), SQLite базата (ако има) се презаписва, HTML файлът се регенерира и `mtime`-ва се, след което браузърът се пренасочва към обичайния `/report/<filename>`.
- За **динамични** справки самата HTML страница не съдържа данните — тя изпраща AJAX заявки към `/api/filter/<report_name>`, `/api/unique/<report_name>/<column>`, `/api/stats/<report_name>`, които `QueryManager` обслужва директно от SQLite базата на справката (без да пипа MSSQL при всяко филтриране).

---

## Нива на достъп

Три нива, контролирани от един query/JSON параметър `key`:

| Ниво | Директория | Ключ (`ACCESS_KEYS`) | Достъпни маршрути |
|-------|------------|------------------------|----------------------|
| `public` | `output/` | *(няма нужда от ключ)* | `/` |
| `private` | `private_output/` | `12345` (пример в кода — **сменете!**) | `/internal?key=...` |
| `secret` | `secret_output/` | `99999` (пример в кода — **сменете!**) | `/secret?key=...` |

Достъпът е **кумулативен по посока нагоре**: `secret` вижда всичко (`public` + `private` + `secret`), `private` вижда `public` + `private`. Проверката се извършва навсякъде чрез сравнение на индекси в списъка `["public", "private", "secret"]`.

Нивото на конкретна справка се определя **автоматично по това в коя директория живее** (`get_report_access`) — не е записано в самата справка. Ключът се приема или като GET параметър (`?key=...`), или като JSON поле `key` в POST тялото — удобно е за AJAX извиквания.

---

## Модул по модул

### `Config.py` / `db_config.py`

`Config.py` дефинира всички работни директории на системата (шаблон, output/private_output/secret_output, databases, logs, metadata, queries, xlsx) като `Path` обекти, **абсолютни и специфични за конкретна машина** (`D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\...`), плюс автоматично създава липсващите с `.mkdir(exist_ok=True)` при import.

`db_config.py` чете `DB_USERNAME`/`DB_PASSWORD` от средата и изгражда две готови MSSQL connection strings (`MSSQL_CONN_STR` за StabiDi, `KODIMA_CONN_STR` за Kodima база), плюс helper `get_engine(conn_str)`.

```python
import os
os.environ["DB_USERNAME"] = "sa"
os.environ["DB_PASSWORD"] = "..."

from db_config import MSSQL_CONN_STR, get_engine
engine = get_engine(MSSQL_CONN_STR)
```

---

### `Load_from_External_File.py`

Минималистичен Tkinter file picker — единствената му задача е да върне път до файл, поддържащ всички формати на системата (вкл. `.sql`):

```python
from Load_from_External_File import Load_From_External_File

picker = Load_From_External_File()
path = picker.select_file()
if path:
    print(f"Избран файл: {path}")
```

---

### `loader.py`

`FileProcessor.load_file(...)` е универсалният вход за зареждане на данни — маршрутизира по разширение (`.xlsx`/`.xls`, `.csv`, `.json`, `.parquet`, `.xml`) или изпълнява `.sql` файл срещу подаден `db_engine`/`connection_string`.

`DataLoader` (наследник) добавя поддръжка за **параметризирани** SQL файлове с `:named` bind променливи:

```python
from loader import DataLoader
from db_config import MSSQL_CONN_STR

loader = DataLoader()

# Обикновен файл
df = loader.load("data/report.xlsx")

# Параметризирана SQL заявка (:warehouse, :date_from и т.н.)
df = loader.load_sql_with_params(
    "sql_queries/overdue_by_partner.sql",
    connection_string=MSSQL_CONN_STR,
    params={"warehouse": 12, "date_from": "01.06.2026"},
)
```

`_coerce_sql_params` автоматично разпознава дати в `%Y-%m-%d` или `%d.%m.%Y` формат и ги превръща в `date` обекти за коректно bind-ване от SQLAlchemy.

---

### `DataFrame_Handler.py`

- **`DataTransformer`** — обвивка на високо ниво: `clean_data` (маха напълно празни редове), `apply_aggregations` (groupby + agg).
- **`DataFrameHandler`** — тежката логика по анализ на колони:
  - `detect_date_columns` — пробва серия дато-формати (`%d.%m.%Y`, `%Y-%m-%d`, ISO с час, `%d/%m/%Y`), избира формата с най-висок процент успешно парснати стойности; ако ≥ 90% съвпадение → превръща колоната в Unix timestamp (милисекунди) за компактно съхранение и бързо сортиране в SQLite/JS.
  - `detect_numeric_columns` — разпознава числа дори когато са записани като текст с валутен символ (`€`, `$`, `£`, `¥`, `лв`) или водещи/крайни интервали; **изисква 100% съвпадение** в непразните стойности (`numeric_mask.all()`), за да класифицира колоната като числова — предпазва от грешно "изтичане" на текстови колони.
  - `round_numeric_columns` — закръгля до 5 знака след десетичната.
  - `calculate_descriptive_stats` — за всяка колона: `total`, `unique`, `empty`; за числови — `min`/`max`/`avg`/брой положителни/отрицателни/нулеви + честоти; за дати — `min`/`max` + честоти по ден; за текст — честоти на стойностите.

```python
from DataFrame_Handler import DataFrameHandler
import pandas as pd

handler = DataFrameHandler()
df, date_cols, date_meta = handler.detect_date_columns(df)
numeric_cols, _ = handler.detect_numeric_columns(df, skip_columns=date_cols)
stats = handler.calculate_descriptive_stats(df, date_cols, numeric_cols)
```

---

### `sqlite_injector.py`

`SQLiteInjector` управлява персистирането на "динамичните" (≥ 10 000 реда) справки в **самостоятелна SQLite база на справка** (`databases/<report_name>.sqlite`):

- `create_table_from_df` — създава празна таблица само по схема (0 реда).
- `inject_data` — **пълен rebuild** (`if_exists='replace'`): датите се нормализират до Unix ms, числата се закръгляват **преди** записа (важна поправка спрямо по-стара версия, документирана изрично в коментарите на кода), после записва на chunk-ове от 5000 реда и пресъздава индексите.
- `append_data` — добавя нови редове към съществуваща таблица без пълен rebuild: подравнява входящите колони към вече съществуващата схема чрез `reindex` (непознати входни колони се пропускат, липсващите се добавят като празни), и **задължително пуска `ANALYZE`** след добавянето — без това SQLite query planner-ът остава с остарели статистики и `ORDER BY ... LIMIT` може да върне грешно сортирани/orphaned резултати спрямо новодобавените редове.
- Всяка връзка минава през `_get_connection()`, която активира `WAL` journal mode, `synchronous=NORMAL`, голям `cache_size` и `temp_store=MEMORY` за производителност, плюс регистрира custom SQL функции (`LOWER`, `DATE_ISO` — виж `query_manager.register_sqlite_user_functions`), така че expression-индексите да съвпадат буквално с това, което заявките после ползват.
- `db_log` пише в `DB_LOG` (`logs/db_log.csv`) CSV одитен лог с таймстамп, път до базата, име на таблица и съобщение.

```python
from sqlite_injector import SQLiteInjector

injector = SQLiteInjector("databases/sales_2026.sqlite")
injector.inject_data(df, table_name="sales_2026")       # пълен rebuild
injector.append_data(new_rows_df, table_name="sales_2026")  # инкрементално добавяне
```

---

### `query_manager.py`

`QueryManager` е сърцето на **сървърното филтриране** за динамичните справки — превръща заявки от DataTables front-end-а (pagination, сортиране, global search, per-column филтри, вложени `SearchBuilder` критерии) в динамично построен, безопасно escape-нат SQL върху SQLite:

- `build_dynamic_query(table_name, filters, sort_by, search_value, text_columns, limit, offset, sb_state, numeric_column_indices, date_column_indices)` → връща `(main_query, count_query)`.
- `_parse_sb_criteria` — рекурсивно превръща JSON дървото на DataTables **SearchBuilder** (вложени `AND`/`OR` групи) в SQL `WHERE` изрази, с типово-специфична логика за `date` (конвертира ISO низове в Unix ms чрез `_iso_to_ts_ms`), числа и текст.
- `get_column_stats` — описателна статистика **и в глобален, и във филтриран разрез** едновременно (напр. `max`/`f_max`, `avg`/`f_avg`) — позволява на UI-то да показва "статистика на филтрираните данни" без отделна заявка за всичко.
- `get_group_subtotals` — междинни суми по йерархия от групиращи колони (`A`, `A|B`, `A|B|C` ключове в резултата) — за групиране "на живо" в таблицата, независимо от pagination.
- `get_unique_values` — уникални стойности на колона (за каскадни/dependent филтри), с изключване на текущия филтър върху самата колона.
- **Автоматично индексиране**: `_create_index_safe` създава композитни индекси при групиране във фонов `ThreadPoolExecutor`, следи ги в служебна таблица `index_usage` и поддържа таван от **максимум 10 индекса на таблица** — при надвишаване се маха най-отдавна използваният (LRU eviction).

```python
from query_manager import QueryManager

qm = QueryManager("databases/sales_2026.sqlite")
main_q, count_q = qm.build_dynamic_query(
    "sales_2026",
    filters={"Region": "София"},
    sort_by="Date",
    limit=50,
    offset=0,
    numeric_column_indices=[3, 4],
    date_column_indices=[1],
)
df_page = qm.execute_query(main_q)
total = qm.get_count(count_q)
```

---

### `parameter_loader.py` / `parameter_resolver.py`

Двойка модули, обслужващи **параметризирани справки** (справки с `:named` bind променливи, чиито стойности потребителят избира преди изпълнение):

- `parameter_resolver.validate_parameter_value` — валидира и нормализира суровата стойност спрямо декларирания `type` на параметъра (`date`, `number`, `checkbox`, `select`); `resolve_default` поддържа относителни дати във формат `today`, `today+N`, `today-N` (чрез `TODAY_PATTERN` regex) — удобно за default-и от рода "последните 90 дни".
- `parameter_loader.load_parameter_values` — за параметри с **динамичен** източник (`"query"` или `"source": {"type": "sql", "query": "..."}`), изпълнява SQL заявката срещу MSSQL и връща или списък `{value, label}` (за `type: select` — dropdown опции), или единична `{value: ...}` (напр. изчислен default).

```python
from parameter_loader import load_parameter_values

param_def = {
    "name": "warehouse",
    "type": "select",
    "query": "SELECT ID as value, Name as label FROM Objects WHERE Deleted = 0",
}
result = load_parameter_values(param_def)
# result.is_select_options == True
# result.data == [{"value": 1, "label": "Склад 1"}, ...]
```

---

### `report_template.pyw`

Batch входна точка за (пре)генериране на справки без уеб сървър — виж [Как работи](#1-генериране-на-справка-batch) по-горе. Дефинира и `input_output_files` списък в `if __name__ == "__main__"` за фиксирани, предварително известни справки (подходящо за Windows Task Scheduler/cron задача, стартираща целия файл периодично).

---

### `parameter_editor.pyw`

Самостоятелен Tkinter desktop инструмент за **визуално създаване/редакция** на JSON файловете с дефиниции на параметри на справка (същия формат, който `report_model.Report` очаква — виж следващата секция). Позволява:

- Задаване на заглавие и категория на справката.
- Добавяне/редакция/изтриване на параметри (`name`, `label`, `type` ∈ {`date`, `select`, `number`, `checkbox`}, `default`).
- За `type == "select"`: или статичен списък от `{value, label}` опции, или SQL заявка за динамично зареждане на опциите.
- Зареждане на съществуващ JSON за редакция, запис на нов/променен JSON.

Спестява ръчно писане на JSON и намалява риска от синтактични грешки при добавяне на нови параметризирани справки.

---

### `Flask_Report.pyw`

Главното уеб приложение — виж [API справочника](#api-справочник-flask) по-долу за пълен списък на маршрутите. Допълнителни бележки:

- Стартира се като `.pyw` (без конзолен прозорец) и добавя **икона в системния трей** (`pystray`) с меню за "Restart" (`os.execv` — рестартира целия процес) и "Exit" (`os._exit(0)`); tooltip-ът показва всички локални IP адреси, на които сървърът слуша, за удобство при споделяне в локалната мрежа.
- Flask работи в **отделна нишка** (`threading.Thread(..., daemon=True)`), докато главната нишка блокира на трей иконата (`icon.run()`) — типичен модел за desktop-подобно приложение около уеб сървър.
- `REPORT_CATEGORIES` е fallback речник за категория по фиксирано име на справка; реалният източник е `metadata/<report_name>.json` (записван от `report_template.pyw` / `parameter_editor.pyw`), ако съществува.

---

### `template_Table_to_HTML.html`

Огромен (≈ 500 KB, > 11 000 реда), самодостатъчен HTML шаблон, попълван от `generator.py` (не е включен в тази документация) чрез placeholder-и от вида `{{FILE_NAME}}`, `{{ROW_COUNT}}`, `{{COLUMN_COUNT}}`, `{{FILTER_HEADERS}}`, `{{TABLE_DATA}}`, `{{IS_DYNAMIC}}`, `{{HAS_PARAMETERS}}`, `{{REPORT_PARAMETERS}}`, `{{DATE_COLUMNS}}`, `{{NUMERIC_COLUMNS}}`, `{{DESCRIPTIVE_STATS}}`, `{{DATE_TIME_NOW}}`, `{{INPUT_FILE_NAME_WITH_EXTENSION}}`.

Изгражда се върху **Bootstrap 5** + **DataTables 2.2.2** с почти пълния набор официални разширения:

| Разширение | Предназначение в шаблона |
|-------------|-----------------------------|
| Buttons + JSZip + xlsx-js-style + pdfmake | Експорт на таблицата в Excel/PDF/CSV, печат |
| SearchBuilder | Визуален конструктор на вложени AND/OR филтри (същият формат, който `query_manager._parse_sb_criteria` разбира) |
| SearchPanes | Панели с бързи чекбокс филтри по колона |
| DateTime | Date/time picker-и в колонните филтри |
| Select | Маркиране/избор на редове |
| FixedColumns / FixedHeader | Замразени колони/хедър при скрол на широки таблици |
| ColReorder | Пренареждане на колони с drag & drop |
| RowGroup | Групиране на редове (в комбинация с `group_subtotals` от бекенда) |
| Select2 | Подобрени dropdown-и за параметрите на справката |

Header секцията показва брой редове/колони, източник, дата на експорт; при статичен режим данните са вградени директно в `{{TABLE_DATA}}` (client-side DataTables), докато при динамичен режим същата JS логика тегли страници от `/api/filter/<report_name>` и субтотали от бекенда вместо да разчита на локален масив.

---

## Формат на JSON метаданните за параметризирани справки

Файлът, който `parameter_editor.pyw` записва и `report_model.Report` (не е включен в тази документация) най-вероятно чете, изглежда така:

```json
{
    "title": "Клиенти с просрочия",
    "category": "Просрочия",
    "parameters": [
        {
            "name": "date_from",
            "label": "Начална дата",
            "type": "date",
            "default": "today-90"
        },
        {
            "name": "warehouse",
            "label": "Склад",
            "type": "select",
            "query": "SELECT ID as value, Name as label FROM Objects WHERE Deleted = 0"
        },
        {
            "name": "min_amount",
            "label": "Минимална сума",
            "type": "number",
            "default": 0
        },
        {
            "name": "only_active",
            "label": "Само активни",
            "type": "checkbox",
            "default": true
        }
    ]
}
```

Файлът се съхранява в `metadata/<report_name>.json` (същата директория, ползвана и за категорията от `report_template.pyw` — двата записа могат да съжителстват, стига полетата да не се презаписват взаимно).

---

## API справочник (Flask)

| Маршрут | Метод | Изисква достъп | Описание |
|----------|-------|------------------|----------|
| `/` | GET | public | Портал — публични справки, групирани по категория. |
| `/internal?key=...` | GET | private | Портал — public + private справки. |
| `/secret?key=...` | GET | secret | Портал — public + private + secret справки. |
| `/report/<filename>` | GET | според директорията на файла | Сервира конкретен готов HTML отчет. |
| `/report/live/<report_name>` | GET | според нивото на справката | Реизпълнява SQL-а на справката срещу MSSQL, обновява SQLite (ако е динамична) и HTML файла, после пренасочва към `/report/<filename>`. |
| `/api/report` | POST (JSON) | според `report` в тялото | Изпълнява (параметризирана) справка изцяло и връща данни + описателна статистика. |
| `/api/report/<report_name>/parameters` | GET | според справката | Връща актуалните дефиниции на параметрите ѝ (заглавие, категория, параметри). |
| `/api/report/parameter-values` | POST (JSON) | опционално, ако е подаден `report` | Изпълнява SQL за динамичен източник на един параметър (dropdown опции или изчислен default). |
| `/api/filter/<report_name>` | GET | според справката | Сървърно филтриране/сортиране/pagination + междинни суми върху SQLite базата на справката (за динамични справки). |
| `/api/unique/<report_name>/<column_name>` | GET | според справката | Уникални стойности на колона (каскадни филтри), при текущо приложени други филтри. |
| `/api/stats/<report_name>` | GET | според справката | Описателна статистика по колона (глобална + филтрирана), поддържа същите филтърни query параметри като `/api/filter`. |

Всички AJAX маршрути приемат `key` параметъра както в GET query string, така и в JSON тялото на POST заявката (`get_access_level()`).

---

## Статичен срещу динамичен режим на справка

| | Статичен (`< 10 000` реда) | Динамичен (`≥ 10 000` реда) |
|---|---|---|
| Съхранение на данните | Вградени директно в HTML (`{{TABLE_DATA}}`) | `databases/<report_name>.sqlite` |
| Филтриране/сортиране | Изцяло на клиента (DataTables в браузъра) | Сървърно, през `/api/filter/<name>` (`QueryManager`) |
| Скорост на отваряне |Zero-latency (статичен файл) | Първоначален shell + AJAX за данните |
| "Live" обновяване | Регенерира изцяло HTML-а | Презаписва SQLite (`if_exists='replace'`) + regenерира shell |
| Подходящо за | Малки/средни, рядко обновявани справки | Големи таблици, чести филтри, справки с милиони редове |

Границата (`10000`) е твърдо закодирана в `report_template.generate_report` и в `Flask_Report._execute_report_query` (проверката там е индиректна — през наличието на `databases/<name>.sqlite`).

---

## Автоматично индексиране в SQLite

`query_manager.should_index(total, distinct, top_freq)` решава дали дадена текстова колона заслужава `LOWER(...)` expression-индекс, за да останат индексите малко на брой и полезни:

- Пропуска колони с по-малко от 20 уникални стойности (твърде "плитки" за индекс).
- Пропуска колони, при които уникалните стойности са под 1% от общия брой редове (почти уникален ключ — индексът не помага достатъчно за филтриране по равенство).
- Пропуска колони, при които най-честата стойност заема над 30% от всички редове (силно "накривена" разпределение — индексът дава малка селективност).

Числовите колони получават `CAST(... AS REAL)` индекс, датовите — обикновен индекс върху нормализираната Unix ms стойност. За групиращите заявки (`get_group_subtotals` / subtotal режим в UI) индексите се създават **асинхронно** (фонов `ThreadPoolExecutor`), за да не блокират текущата заявка, с максимум 10 активни индекса на таблица и LRU политика за подмяна.

---

## Конфигурация и променливи на средата

| Променлива на средата | Използва се от | Описание |
|--------------------------|--------------------|----------|
| `DB_USERNAME` | `db_config.py` | SQL Server потребител за `MSSQL_CONN_STR`/`KODIMA_CONN_STR`. |
| `DB_PASSWORD` | `db_config.py` | SQL Server парола (**внимание**: подава се сурова, без `quote_plus` escape — виж известните особености). |

Директориите в `Config.py` в момента са **твърдо закодирани абсолютни пътища** (`D:\Stoyan\SQLScript\SatbiDi\Table_to_WEB_2\...`) — преди преместване на проекта на друга машина или в контейнер, тези пътища трябва да се параметризират (напр. през `os.environ` с fallback към относителен път спрямо `Path(__file__).parent`).

Ключовете за достъп (`ACCESS_KEYS` в `Flask_Report.pyw`) също са хардкоднати в изходния код (`"12345"`, `"99999"`) — препоръчително е да се преместят в среда/`.env` файл, особено за `secret` нивото.

---

## Инсталация и зависимости

Синтезирано от `import`-ите във всички подадени файлове (няма `pyproject.toml`/`requirements.txt` сред подадените файлове за тази система):

```bash
pip install flask pandas sqlalchemy pyodbc pillow pystray winotify
```

| Пакет | Използва се за |
|--------|-------------------|
| `flask` | Уеб порталът и AJAX API |
| `pandas` | Зареждане, трансформация, `to_sql`/`read_sql` навсякъде |
| `sqlalchemy` | MSSQL engine + `text()` bind параметри |
| `pyodbc` | ODBC драйвер за SQLAlchemy → SQL Server (изисква инсталиран **ODBC Driver 17 for SQL Server**) |
| `pillow` (`PIL`) | Генериране на иконата за системния трей |
| `pystray` | Икона и меню в системния трей на `Flask_Report.pyw` |
| `winotify` | Windows toast известия при завършено генериране (`report_template.pyw`) — **само Windows** |
| `openpyxl` (имплицитно, чрез `pandas.read_excel`) | Четене на `.xlsx` |
| `pyarrow` (имплицитно, чрез `pandas.read_parquet`) | Четене на `.parquet` |

> `winotify` и `pystray`-трей интеграцията ограничават `report_template.pyw`/`Flask_Report.pyw` до **Windows** среда. Останалите модули (`loader.py`, `DataFrame_Handler.py`, `sqlite_injector.py`, `query_manager.py`, `parameter_loader.py`, `parameter_resolver.py`) са платформено независими.

---

## Стартиране

**Уеб порталът:**

```bash
python Flask_Report.pyw
```

Стартира Flask на `http://0.0.0.0:5010` (виж бележка за `debug=True` в [Известни особености](#известни-особености--технически-дълг)) и добавя икона в системния трей. Адресите за отваряне от локалната мрежа се виждат в tooltip-а на трей иконата.

**Ръчна/пакетна генерация на справка:**

```bash
python report_template.pyw
```

Изпълнява предварително дефинирания в `if __name__ == "__main__"` списък от `(вход, изход)` файлове. За автоматизация — планирайте периодично изпълнение чрез Windows Task Scheduler.

**Редакция на параметри на справка:**

```bash
python parameter_editor.pyw
```

---

## Липсваща документация (модули извън обхвата на този README)

Следните модули се импортират и активно се използват от системата, но не са били подадени за тази документация — описанието им по-горе е **изведено единствено от начина, по който се извикват**, не от прегледан код:

- **`generator.py`** (класове `HTMLGenerator`, `DataTableGenerator`) — попълва `template_Table_to_HTML.html` с реалните данни/метаданни. Публичен интерфейс, установен по употреба: `generate_static_report(file_in, df, file_out)`, `generate_dynamic_template(file_in, df, file_out, report_name, is_dynamic_override=...)`.
- **`report_model.py`** (клас `Report`) — представлява дефиницията на параметризирана справка. Установен по употреба: `Report.load(report_name)`, свойства `.sql`, `.has_parameters`, `.title`, `.category`; методи `.validate_parameters(raw)`, `.default_parameters()`, `.parameter_definitions()`.

При наличие на тези два файла, README-то може да се разшири с пълна секция за тях.

---

## Известни особености / технически дълг

При прегледа на подадените файлове бяха забелязани следните точки:

- **`encoding="ANSI"` не е валидно име на кодировка в Python** (`report_template.py: log_success`/`log_error`, `loader.py: load_file` за `.csv`). Python/pandas очакват конкретно име на кодова таблица (напр. `"cp1251"` за кирилица на Windows), а `"ANSI"` предизвиква `LookupError: unknown encoding: ANSI`. В `loader.py` това е "случайно защитено" от `try/except`, който пада обратно към `sep=","` при грешка — но в `report_template.log_success`/`log_error` **няма** такава защита: ако `log_success(...)` хвърли `LookupError` след успешно генериран отчет, изключението се хваща от външния `except`, който на свой ред вика `log_error(...)` **със същата невалидна кодировка** — втора грешка, която вече не се прихваща никъде и ще прекъсне изпълнението.
- **`Flask_Report.pyw` стартира с `debug=True` и `host="0.0.0.0"`** — това означава, че Werkzeug debugger-ът (с интерактивна конзола, позволяваща изпълнение на произволен Python код) е достъпен по мрежата за всеки, който познава IP-то и порта, независимо от нивата на достъп `public`/`private`/`secret` на самите справки. За система с `secret`-ниво данни това е сериозен риск за производствена среда.
- **Хардкоднати ключове за достъп** (`ACCESS_KEYS = {"private": "12345", "secret": "99999"}`) направо в изходния код — освен слаби, при качване на кода в система за контрол на версиите остават видими в историята дори след последваща смяна.
- **`db_config.py` не escape-ва паролата** (`quote_plus`) при построяване на `MSSQL_CONN_STR`/`KODIMA_CONN_STR` — същият клас проблем, който беше идентифициран и коригиран в `stabil_db.Login_Form_SQL_GUI`: специален символ в `DB_PASSWORD` (`@`, `:`, `/`, `#` и др.) би счупил connection string-а.
- **Твърдо закодирани абсолютни пътища** в `Config.py`, специфични за конкретна Windows машина (`D:\Stoyan\SQLScript\...`) — пречат на преносимост между машини/среди без ръчна редакция на файла.
- **`Load_from_External_File.py` дублира функционалност**, която вече съществува в отделния пакет `file_dialogs_lib` (документиран по-рано) — обмислете консолидация в едно място, за да не се разминават филтрите за файлови типове между двата модула.
- **Границата от `10000` реда за статичен/динамичен режим е дублирана** на две места (`report_template.generate_report` буквално, `Flask_Report._execute_report_query` — индиректно, чрез съществуването на `.sqlite` файла) — препоръчително е да се изнесе като именувана константа в `Config.py`, за да няма риск от разминаване между batch и live генерирането.
