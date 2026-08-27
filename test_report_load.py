
from report_model import Report
from pathlib import Path

report_name = "Примерна Параметризирана Справка"

print(f"Търсим справка: {report_name}")
print(f"Текуща директория: {Path.cwd()}")

report = Report.load(report_name)

print(f"report is None: {report is None}")
if report:
    print(f"report.has_parameters: {report.has_parameters}")
    print(f"report.parameters: {report.parameters}")
