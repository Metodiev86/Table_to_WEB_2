from Master_Creater_SQL_to_XLSX import *

QUERY = """SELECT CAST(Oper.Date AS DATE) AS 'Дата', Us.Name AS 'Оператор', obj.Name AS 'Обект', COUNT(DISTINCT oper.Acct) AS 'Брой продажби', SUM(oper.qtty * oper.Sign * oper.PriceOut)*(-1) AS 'Сума'
FROM Operations as oper
Join Users as us ON Us.ID = Oper.operatorID
Join Objects as obj ON Obj.ID = Oper.ObjectID
WHERE Oper.OperType = 2 
Group By Us.Name, Obj.Name, Oper.Date
Order By CAST(oper.Date AS DATE) DESC, obj.Name, Us.Name"""


OUTPUT_FILE = 'Продажби по Оператори АРХИВ.xlsx'
OUTPUT_PATH = fr'{XLSX_DIR}/{OUTPUT_FILE}'


query_df = create_df(QUERY, my_engine)
export_to_excel(query_df, OUTPUT_PATH)