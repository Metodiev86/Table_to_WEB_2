SELECT 
      [Date] AS 'Дата'
	  ,[Acct] AS 'Стокова'
	  ,g.Code AS 'Код'
      ,g.[Name] AS 'Артикул'
	  ,par.Company As 'Партньор'
      ,obj.[Name] AS 'Обект'
      ,operator.Name AS 'Оператор'
	  ,oper.Qtty AS 'Количество'
      ,Round(oper.PriceOut, 2) AS 'Продажна'
      ,g.PriceOut10 AS 'Ценова 8'
	  ,ROUND(oper.PriceOut - g.PriceOut10, 2) AS 'Разлика'
	  ,oper.Qtty * ROUND(oper.PriceOut - g.PriceOut10, 2) AS 'Сума'
  FROM [StabiDi_Original].[dbo].[Operations] AS oper 
  INNER join Goods AS g ON g.ID = oper.GoodID
  INNER JOIN Partners AS par ON par.ID = oper.PartnerID
  INNER JOIN [Objects] AS obj ON obj.ID = oper.ObjectID
  INNER JOIN [Users] AS operator ON operator.ID = oper.OperatorID
  INNER JOIN [Users] AS us ON us.ID = oper.UserID
  WHERE Date = CAST(GETDATE() - 1 AS DATE) and oper.OperType = 2 and (ROUND(oper.PriceOut, 2) - g.PriceOut10) < -0.01 and g.[Type] = 0
  Order BY oper.[Date], Acct