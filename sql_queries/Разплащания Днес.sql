SELECT [Acct] as "Стокова"
      ,operT.BG AS 'Операция'
      ,par.Company AS 'Партньор'
      ,SUM(Qtty * [Mode] * [Sign]) AS 'Сума'
      ,[Date] AS 'Дата'
      ,us.[Name] AS 'Оператор'
      ,obj.[Name] AS 'Обект'
      ,payT.[Name] AS 'Тип'
      ,[EndDate] AS 'Падеж'
  FROM [StabiDi_Original].[dbo].[Payments] as pay

  JOIN OperationType as operT on operT.ID = pay.OperType
  JOIN Partners as par on par.ID = pay.PartnerID
  JOIN Users AS us on us.ID = pay.UserID
  JOIN [Objects] as obj ON obj.ID = pay.ObjectID
  JOIN PaymentTypes as payT on payT.ID = pay.[Type]
  WHERE [Date] = CAST(CURRENT_TIMESTAMP AS DATE)
  GROUP BY Acct, operT.BG, par.Company, [Date], us.[Name], obj.[Name], payT.[Name], EndDate
  ORDER BY Acct