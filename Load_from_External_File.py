import tkinter as tk
from tkinter import filedialog, messagebox

class Load_From_External_File:
		def __init__(self):
				self.file_path = None

		def select_file(self):
				root = tk.Tk()
				root.withdraw()  # hide main window

				self.file_path = filedialog.askopenfilename(
						title="Select Data File",
						filetypes=[
								("All Supported", "*.xlsx *.xls *.csv *.json *.parquet *.xml *.sql"),
								("Excel files", "*.xlsx *.xls"),
								("CSV files", "*.csv"),
								("XML files", "*.xml"),
								("JSON files", "*.json"),
								("Parquet files", "*.parquet"),
								("SQL Query files", "*.sql")
						],
				)

				return self.file_path