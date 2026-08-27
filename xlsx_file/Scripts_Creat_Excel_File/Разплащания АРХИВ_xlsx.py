from Master_Creater_SQL_to_XLSX import *

QUERY = """SELECT [Acct] as "Стокова"
      ,operT.BG AS 'Операция'
      ,par.Company AS 'Партньор'
      ,SUM(Qtty * [Mode] * [Sign]) AS 'Сума'
      ,CAST([Date] AS DATE) AS 'Дата'
      ,us.[Name] AS 'Оператор'
      ,obj.[Name] AS 'Обект'
      ,payT.[Name] AS 'Тип'
      ,CAST([EndDate] AS DATE) AS 'Падеж'
  FROM [StabiDi_Original].[dbo].[Payments] as pay

  JOIN OperationType as operT on operT.ID = pay.OperType
  JOIN Partners as par on par.ID = pay.PartnerID
  JOIN Users AS us on us.ID = pay.UserID
  JOIN [Objects] as obj ON obj.ID = pay.ObjectID
  JOIN PaymentTypes as payT on payT.ID = pay.[Type]
  GROUP BY Acct, operT.BG, par.Company, CAST([Date] AS DATE), us.[Name], obj.[Name], payT.[Name], CAST(EndDate AS DATE)
  ORDER BY Acct
"""

OUTPUT_FILE = 'Разплащания АРХИВ.xlsx'
OUTPUT_PATH = fr'{XLSX_DIR}/{OUTPUT_FILE}'


query_df = create_df(QUERY, my_engine)
export_to_excel(query_df, OUTPUT_PATH)