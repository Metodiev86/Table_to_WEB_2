SELECT DISTINCT
    pay.Acct AS 'Стокова No',
    doc.invoiceNumber AS 'Фактура',
    par.Company AS 'Партньор',
    par.Bulstat AS 'ЕИК',
    (oper.qtty * oper.sign * (-1) * oper.priceOut) AS 'Обща Стойност',
    obj.[Name] AS 'Обект',
    users.[Name] AS 'Оператор',
    oper.[Date]  AS 'Дата',
    operType.BG AS 'Операция'
    
FROM Payments pay
JOIN Documents doc ON pay.Acct = doc.Acct AND doc.OperType = pay.OperType
JOIN Partners par ON pay.PartnerID = par.ID
JOIN Operations oper ON pay.Acct = oper.Acct AND oper.OperType = pay.OperType
JOIN OperationType operType ON pay.OperType = operType.ID
JOIN Goods god ON god.ID = oper.GoodID
JOIN Objects obj ON obj.Id = oper.ObjectID
JOIN Users users ON users.Id = oper.UserID
WHERE oper.OperType IN (2,16,26,27)
  AND god.Id = 7
GROUP BY
    pay.Acct, obj.[Name], god.[Name], par.Company, par.Bulstat,
    oper.OperType, operType.BG, oper.[Date],
    users.[Name], doc.InvoiceNumber,
    oper.Qtty, oper.PriceOut, oper.[Sign]
ORDER BY  oper.[Date]

