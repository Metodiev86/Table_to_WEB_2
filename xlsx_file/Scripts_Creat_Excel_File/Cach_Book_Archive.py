from Master_Creater_SQL_to_XLSX import *

QUERY = """SELECT 
    [Date] AS 'Дата',

    -- Описание
    CASE 
        WHEN d.pos > 0 
        THEN LEFT([Desc], d.pos - 1)
        ELSE [Desc]
    END AS 'Описание',

    -- Партньор
    CASE 
        WHEN d.pos > 0 
        THEN LTRIM(SUBSTRING([Desc], d.pos + 1, LEN([Desc])))
        ELSE NULL
    END AS 'Партньор',

    operT.Name AS 'Операция',
    [Sign] * [Profit] AS 'Сума',
    us.Name AS 'Потребител',
    obj.Name AS 'Обект'

FROM [StabiDi_Original].[dbo].[CashBook] AS cash

CROSS APPLY (
    SELECT 
        CASE 
            WHEN CHARINDEX(',', [Desc]) = 0 THEN CHARINDEX('/', [Desc])
            WHEN CHARINDEX('/', [Desc]) = 0 THEN CHARINDEX(',', [Desc])
            ELSE 
                CASE 
                    WHEN CHARINDEX(',', [Desc]) < CHARINDEX('/', [Desc]) 
                    THEN CHARINDEX(',', [Desc])
                    ELSE CHARINDEX('/', [Desc])
                END
        END AS pos
) d

JOIN StabiDi_Log.dbo.Operations AS operT ON operT.ID = cash.OperType
JOIN Users AS us ON us.ID = cash.UserID
JOIN [Objects] AS obj ON obj.ID = cash.ObjectID
"""


OUTPUT_FILE = 'Касова Книга АРХИВ.xlsx'
OUTPUT_PATH = fr'{XLSX_DIR}/{OUTPUT_FILE}'


query_df = create_df(QUERY, my_engine)
export_to_excel(query_df, OUTPUT_PATH)