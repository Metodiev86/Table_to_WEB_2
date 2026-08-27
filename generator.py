# generator.py
import json
import math
from pathlib import Path
import pandas as pd
import datetime
from DataFrame_Handler import DataFrameHandler
from report_model import Report
class HTMLGenerator:
    def __init__(self, template_path: str):
        self.template_path = Path(template_path)
        self.template = self.template_path.read_text(encoding="utf-8")

    def _report_parameter_payload(self, report_name: str) -> tuple[list, bool]:
        report = Report.load(report_name)
        if report and report.has_parameters:
            return report.parameter_definitions(), True
        return [], False

    def _common_replacements(
        self,
        df: pd.DataFrame,
        input_file: str,
        report_name: str,
        date_columns,
        numeric_columns,
        column_metadata,
        is_dynamic: bool,
        table_data_json: str,
        descriptive_stats_json: str,
    ) -> dict:
        headers = df.columns.tolist()
        param_defs, has_parameters = self._report_parameter_payload(report_name)
        return {
            "{{TABLE_DATA}}": table_data_json,
            "{{DESCRIPTIVE_STATS}}": descriptive_stats_json,
            "{{FILTER_HEADERS}}": "\n".join(f"<th>{col}</th>" for col in headers),
            "{{ROW_COUNT}}": str(len(df)),
            "{{COLUMN_COUNT}}": str(len(headers)),
            "{{FILE_NAME}}": report_name,
            "{{INPUT_FILE_NAME_WITH_EXTENSION}}": Path(input_file).name,
            "{{DATE_TIME_NOW}}": datetime.datetime.now().strftime(" %d.%m.%Y %H:%M:%S"),
            "{{DATE_COLUMNS}}": json.dumps(date_columns),
            "{{NUMERIC_COLUMNS}}": json.dumps(numeric_columns),
            "{{COLUMN_METADATA}}": json.dumps(column_metadata, ensure_ascii=False),
            "{{IS_DYNAMIC}}": "true" if is_dynamic else "false",
            "{{HAS_PARAMETERS}}": "true" if has_parameters else "false",
            "{{REPORT_PARAMETERS}}": json.dumps(param_defs, ensure_ascii=False),
        }

    def generate_static_report(
            self,
            inputFile: str,
            df: pd.DataFrame,
            output_path: str
    ):

        handler = DataFrameHandler()

        # --------------------------------------------------
        # detect + normalize dates
        # --------------------------------------------------

        df, date_columns, column_metadata = (
            handler.detect_date_columns(df)
        )

        # --------------------------------------------------
        # numeric detect
        # --------------------------------------------------

        numeric_columns, currency_columns = (
            handler.detect_numeric_columns(df, date_columns)
        )
        numeric_col_names = [df.columns[i] for i in numeric_columns]
        # НЕ закръгляме тук — пълната прецизност влиза в tableData.
        # Закръгляването е визуален слой в JS (formatNumericDisplay).
        # --------------------------------------------------
        # data
        # --------------------------------------------------



        report_name = Path(inputFile).stem
        html = self.template

        def _convert_scalar(v):
            if v is None:
                return None
            try:
                if pd.isna(v):
                    return None
            except (TypeError, ValueError):
                pass
            try:
                if hasattr(v, 'item'):
                    py_v = v.item()
                    if isinstance(py_v, float) and not math.isfinite(py_v):
                        return None
                    return py_v
            except Exception:
                pass
            if isinstance(v, float) and not math.isfinite(v):
                return None
            return v

        rows = []
        for row in df.itertuples(index=False, name=None):
            rows.append([_convert_scalar(c) for c in row])
        table_data_json = json.dumps(rows, ensure_ascii=False, default=str)

        descriptive_stats = handler.calculate_descriptive_stats(df, date_columns, numeric_columns)
        descriptive_stats_json = json.dumps(
            {str(k): v for k, v in descriptive_stats.items()},
            ensure_ascii=False,
            default=str,
        )

        _, has_parameters = self._report_parameter_payload(report_name)
        replacements = self._common_replacements(
            df,
            inputFile,
            report_name,
            date_columns,
            numeric_columns,
            column_metadata,
            is_dynamic=False,
            table_data_json="[]" if has_parameters else table_data_json,
            descriptive_stats_json="{}" if has_parameters else descriptive_stats_json,
        )

        for key, value in replacements.items():
            html = html.replace(key, value)

        Path(output_path).write_text(
            html,
            encoding="utf-8"
        )

        return output_path

    def generate_dynamic_template(
            self,
            inputFile: str,
            df: pd.DataFrame,
            output_path: str,
            report_name: str = None,
            is_dynamic_override: bool = True
    ):

        handler = DataFrameHandler()

        df_detect, date_columns, column_metadata = (
            handler.detect_date_columns(df)
        )

        numeric_columns, currency_columns = (
            handler.detect_numeric_columns(df_detect, date_columns)
        )
        # НЕ закръгляме — пълната прецизност остава в данните.
        # Закръгляването е визуален слой в JS (formatNumericDisplay).

        if not report_name:
            report_name = Path(inputFile).stem

        html = self.template

        replacements = self._common_replacements(
            df,
            inputFile,
            report_name,
            date_columns,
            numeric_columns,
            column_metadata,
            is_dynamic=is_dynamic_override,
            table_data_json="[]",
            descriptive_stats_json="{}",
        )

        for key, value in replacements.items():
            html = html.replace(key, value)

        Path(output_path).write_text(
            html,
            encoding="utf-8"
        )

        return output_path

class DataTableGenerator(HTMLGenerator):
    def insert_to_html(self, inputFile: str, df: pd.DataFrame, output_path: str):
        return self.generate_static_report(inputFile, df, output_path)

