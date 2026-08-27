from Master_Creater_SQL_to_XLSX import *

QUERY = """SELECT DISTINCT
    pay.Acct AS 'Стокова No',
    doc.invoiceNumber AS 'Фактура',
    par.Company AS 'Партньор',
    par.Bulstat AS 'ЕИК',
    (oper.qtty * oper.sign * (-1) * oper.priceOut) AS 'Обща Стойност',
    obj.[Name] AS 'Обект',
    users.[Name] AS 'Оператор',
    CAST(oper.[Date] AS DATE) AS 'Дата',
    operType.BG AS 'Операция'
    
FROM Payments pay
LEFT JOIN Documents doc ON pay.Acct = doc.Acct AND doc.OperType = pay.OperType
LEFT JOIN Partners par ON pay.PartnerID = par.ID
LEFT JOIN Operations oper ON pay.Acct = oper.Acct AND oper.OperType = pay.OperType
LEFT JOIN OperationType operType ON pay.OperType = operType.ID
LEFT JOIN Goods god ON god.ID = oper.GoodID
LEFT JOIN Objects obj ON obj.Id = oper.ObjectID
LEFT JOIN Users users ON users.Id = oper.UserID
WHERE oper.OperType IN (2,16,26,27)
  AND god.Id = 228
GROUP BY
    pay.Acct, obj.[Name], god.[Name], par.Company, par.Bulstat,
    oper.OperType, operType.BG, oper.[Date],
    users.[Name], doc.InvoiceNumber,
    oper.Qtty, oper.PriceOut, oper.[Sign]
ORDER BY oper.[Date]"""


OUTPUT_FILE = 'Аванс за Стока.xlsx'
OUTPUT_PATH = fr'{XLSX_DIR}/{OUTPUT_FILE}'


query_df = create_df(QUERY, my_engine)
export_to_excel(query_df, OUTPUT_PATH)