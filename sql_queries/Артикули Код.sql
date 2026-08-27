SELECT
	   gr.Name	AS 'Група'
      ,g.[Code] AS 'Код'
      ,g.[Name] AS 'Артикул'
	  ,[BarCode1] AS 'EAN'
      ,[Catalog1] AS 'Кaталог1'
      ,[Catalog3] AS 'Кaталог3'
	  , CASE
			WHEN [Deleted] = 0
				THEN 'Видим'
				ELSE ''
			END AS 'Статус' 
  FROM [StabiDi_Original].[dbo].[Goods] AS g
  INNER JOIN GoodsGroups AS gr ON gr.ID = g.GroupID
  WHERE gr.code LIKE :gGroup + '%'
  ORDER BY g.Code DESC