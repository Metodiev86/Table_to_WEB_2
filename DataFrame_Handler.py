import pandas as pd
import math


class DataTransformer:
	def __init__(self):
		self.handler = DataFrameHandler()

	def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
		# Премахва напълно празни редове
		df = df.dropna(how="all")
		# Тук може да се добави допълнително изчистване
		return df

	def apply_aggregations(self, df: pd.DataFrame, group_by_col: str, agg_dict: dict) -> pd.DataFrame:
		# Изпълнява предварителни изчисления (агрегации), ако са необходими
		if group_by_col in df.columns:
			return df.groupby(group_by_col).agg(agg_dict).reset_index()
		return df

class DataFrameHandler:
	def __init__(self):
		pass

	def round_numeric_columns(self, df: pd.DataFrame, numeric_col_names: list) -> pd.DataFrame:
		"""Закръглява числовите колони до 5 знака след десетичната."""
		for col in numeric_col_names:
			if col in df.columns:
				df[col] = pd.to_numeric(df[col], errors='coerce').round(5)
		return df

	def detect_date_columns(self, df: pd.DataFrame):

		df = df.copy()

		date_columns = []
		column_metadata = {}

		DATE_FORMATS = [
			"%d.%m.%Y",
			"%d.%m.%Y %H:%M:%S",
			"%Y-%m-%d",
			"%Y-%m-%d %H:%M:%S",
			"%d/%m/%Y",
		]

		for i, col in enumerate(df.columns):

			series = df[col]
			dtype = series.dtype

			best_parsed = None
			best_ratio = 0

			# --------------------------------------------------
			# datetime64 колона
			# --------------------------------------------------

			if pd.api.types.is_datetime64_any_dtype(dtype):

				parsed = pd.to_datetime(series, errors="coerce")

				best_parsed = parsed
				best_ratio = 1

			# --------------------------------------------------
			# object/string колона
			# --------------------------------------------------

			elif (
					pd.api.types.is_object_dtype(dtype)
					or pd.api.types.is_string_dtype(dtype)
			):

				original = series

				for fmt in DATE_FORMATS:

					parsed = pd.to_datetime(
						original,
						format=fmt,
						errors="coerce"
					)

					non_null_original = original.dropna()

					if len(non_null_original) > 0:
						ratio = parsed.notna().sum() / len(non_null_original)
					else:
						ratio = 0

					if ratio > best_ratio:
						best_ratio = ratio
						best_parsed = parsed

			# --------------------------------------------------
			# ако е разпозната като дата
			# --------------------------------------------------

			if best_ratio >= 0.9 and best_parsed is not None:
				unix_ms = best_parsed.astype("datetime64[ms]").astype("int64")
				mask = best_parsed.notna()
				df[col] = unix_ms.where(mask, pd.NA)
				date_columns.append(i)


				column_metadata[col] = {
					"physical_type": "number",
					"semantic_type": "datetime",
					"datetime_format": "unix_ms"
				}

		return df, date_columns, column_metadata

	def detect_numeric_columns(self, df: pd.DataFrame, skip_columns: list = None):
		numeric_columns = []
		currency_columns = []
		skip_set = set(skip_columns or [])

		for i, col in enumerate(df.columns):
			if i in skip_set:
				continue
			series = df[col]

			# Ако вече е numeric
			if pd.api.types.is_float_dtype(series) or pd.api.types.is_integer_dtype(series):
				numeric_columns.append(i)
				continue

			# Ако е object/string, опитваме да го превърнем в число
			if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
				# Работим само с непразните стойности
				non_empty = series.dropna()
				non_empty = non_empty[non_empty.astype(str).str.strip() != ""]
				if len(non_empty) == 0:
					continue

				# Почистваме САМО водещи/завършващи интервали и валутни символи (€, $, лв и др.)
				# НЕ премахваме букви вътре в стойността — "ABC123" трябва да остане невалидно
				cleaned = non_empty.astype(str).str.strip()
				cleaned = cleaned.str.replace(r'^[€$£¥лв\s]+|[€$£¥лв\s]+$', '', regex=True)
				cleaned = cleaned.str.replace(r'\s', '', regex=True)  # само вътрешни интервали в числата

				# Валидираме с to_numeric БЕЗ предварително strip на букви
				numeric_mask = pd.to_numeric(cleaned, errors="coerce").notna()
				# ratio = numeric_mask.mean()

				# if ratio >= 0.9:
				# 	numeric_columns.append(i)
				if numeric_mask.all():
					numeric_columns.append(i)

		return numeric_columns, currency_columns

	def calculate_descriptive_stats(self, df: pd.DataFrame, date_columns: list, numeric_columns: list):
		stats_dict = {}

		for i, col in enumerate(df.columns):
			series = df[col]

			# Basic stats for ALL columns
			# Третираме низове само с интервали като празни
			str_series = series.astype(str).str.strip()
			is_empty_mask = (series.isna()) | (str_series == "")

			col_stats = {
				"total": len(series),
				"unique": int(series[~is_empty_mask].nunique()),
				"empty": int(is_empty_mask.sum()),
			}

			# Type-specific stats
			if i in numeric_columns:
				num_series = pd.to_numeric(series, errors="coerce")

				# Format frequency keys to avoid .0 for integers
				freqs = {}
				vc = series.value_counts()
				for val, count in vc.items():
					try:
						f_val = float(val)
						# Ако е цяло число, премахваме .0
						key = str(int(f_val)) if f_val == int(f_val) else str(f_val)
						freqs[key] = int(count)
					except:
						freqs[str(val)] = int(count)

				avg = num_series.mean()

				col_stats.update({
					"type": "numeric",
					"max": float(num_series.max()) if not num_series.isna().all() else None,
					"min": float(num_series.min()) if not num_series.isna().all() else None,
					"avg": float(avg) if pd.notna(avg) and math.isfinite(avg) else None,
					"positives": int((num_series > 0).sum()),
					"negatives": int((num_series < 0).sum()),
					"zeros": int((num_series == 0).sum()),
					"frequencies": freqs
				})

				# col_stats.update({
				# 	"type": "numeric",
				# 	"max": float(num_series.max()) if not num_series.isna().all() else None,
				# 	"min": float(num_series.min()) if not num_series.isna().all() else None,
				# 	"avg": float(num_series.mean()) if not num_series.isna().all() else None,
				# 	"positives": int((num_series > 0).sum()),
				# 	"negatives": int((num_series < 0).sum()),
				# 	"zeros": int((num_series == 0).sum()),
				# 	"frequencies": freqs
				# })
			elif i in date_columns:

				# unix ms -> datetime
				date_series = pd.to_datetime(
					series,
					unit="ms",
					errors="coerce"
				)

				# frequency stats
				freqs = {
					pd.to_datetime(val, unit="ms").strftime("%Y-%m-%d"): int(count)
					for val, count in series.dropna().value_counts().items()
				}

				col_stats.update({
					"type": "date",

					"max": (
						date_series.max().strftime("%Y-%m-%d")
						if pd.notna(date_series.max())
						else None
					),

					"min": (
						date_series.min().strftime("%Y-%m-%d")
						if pd.notna(date_series.min())
						else None
					),

					"frequencies": freqs
				})
			else:
				# Convert frequency keys to string to avoid JSON errors
				freqs = {str(val): int(count) for val, count in series.value_counts().items()}
				col_stats.update({
					"type": "text",
					"frequencies": freqs
				})

			stats_dict[str(col)] = col_stats

		return stats_dict