SELECT
	   gr.Name	AS 'Група'
      ,g.[Code] AS 'Код'
      ,g.[Name] AS 'Артикул'
	  ,[BarCode1] AS 'EAN'
      ,[Catalog1] AS 'Кaталог1'
      ,[Catalog3] AS 'Кaталог3'
      ,[Measure1] AS 'Мярка'
      ,[Ratio] AS 'Разфасовка'
      ,[PriceIn] AS 'Доставна'
      ,[PriceOut1] AS 'Едро'
      ,[PriceOut2] AS 'Дребно'
      ,[PriceOut3] AS 'Ценова 1'
      ,[PriceOut4] AS 'Ценова 2'
      ,[PriceOut10] AS 'Ценова 8'
      , CASE
			WHEN [Deleted] = 0
				THEN 'Видим'
				ELSE ''
			END AS 'Статус' 
  FROM [StabiDi_Original].[dbo].[Goods] AS g
  INNER JOIN GoodsGroups AS gr ON gr.ID = g.GroupID