from Master_Creater_SQL_to_XLSX import *

QUERY = """SELECT DISTINCT  oper.Date AS 'Дата', (pay.Acct) AS 'Стокова No', god.Name As 'Артикул', par.Company AS 'Партньор', (oper.Qtty * oper.Sign)*(-1) as 'Бройки',
                obj.Name AS 'Обект', users.Name As 'Оператор', oper.Note As 'Забележка', operType.BG AS 'Операция'

				/* END SELECT */

FROM Payments as pay
	
	LEFT JOIN Documents AS doc ON pay.Acct = doc.Acct and doc.OperType = pay.OperType
	LEFT JOIN Partners AS par ON Pay.PartnerID = par.ID
	LEFT JOIN Operations AS oper ON pay.Acct = oper.Acct and oper.OperType = pay.OperType
	LEFT JOIN OperationType AS operType ON pay.OperType = operType.ID
    LEFT JOIN Goods As god ON god.ID = oper.GoodID
    LEFT JOIN Objects as obj on obj.Id = oper.ObjectID
	LEFT JOIN Users On Users.Id = oper.UserID

WHERE  
	oper.OperType IN (2, 16, 26, 27)
AND
	doc.invoiceNumber IS NULL
AND 
	god.GroupID in (114)

Group By pay.Acct, god.Name, Obj.Name, god.Name,  par.Company, oper.Qtty, oper.OperType, OperType.BG, oper.Date, users.Name, oper.Note, oper.UserRealTime, doc.InvoiceDate, doc.ExternalInvoiceDate, oper.Sign

HAVING	SUM(pay.Mode * pay.Qtty) <> 0


ORDER BY par.Company, oper.Date
"""

OUTPUT_FILE = 'Палети НЕ фактурирани.xlsx'
OUTPUT_PATH = fr'{XLSX_DIR}/{OUTPUT_FILE}'


query_df = create_df(QUERY, my_engine)
export_to_excel(query_df, OUTPUT_PATH)