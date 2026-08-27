SELECT *
FROM
(
	SELECT DISTINCT
		pay.Acct AS 'Стокова No',
		doc.invoiceNumber AS 'Фактура',
		CAST(oper.[Date] AS DATE)  AS 'Дата',
		par.Company AS 'Партньор',
		par.Bulstat AS 'ЕИК',
		(oper.qtty * oper.sign * (-1) * oper.priceOut) AS 'Обща Стойност',
		obj.[Name] AS 'Обект',
		users.[Name] AS 'Оператор',
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
	  AND (par.Company = :select_partner OR :is_all_parnter = 1)
	GROUP BY
		pay.Acct, obj.[Name], god.[Name], par.Company, par.Bulstat,
		oper.OperType, operType.BG, oper.[Date],
		users.[Name], doc.InvoiceNumber,
		oper.Qtty, oper.PriceOut, oper.[Sign]
) AS subquery
WHERE subquery.Фактура IS NUll OR :not_invoice = 0
ORDER BY  subquery.Дата

