SELECT 
	invoices.pName      AS 'Партньор',
    invoices.invdate    AS 'Дата',
	CASE invoices.dDocType 
        WHEN 0 THEN invoices.invnum 
        ELSE invoices.toinvnum 
    END AS 'Фактура No',

    CASE invoices.dDocType 
        WHEN 2 THEN invoices.invnum 
        ELSE NULL 
    END AS Кредитно,

    CASE invoices.dDocType 
        WHEN 1 THEN invoices.invnum 
        ELSE NULL 
    END AS Дебитно,
    invoices.docnum     AS 'Стокова',
    invoices.EndDate    AS 'Падеж',
    invoices.due_day AS 'Дни Просрочие',
    --invoices.pOperType  AS 'Операция',
    invoices.totalsum   AS 'Сума по Фактура',
    invoices.paidsum    AS 'Платено',
	invoices.paidDate	AS 'Дата на Плащане',
    invoices.operNote	AS 'Курс',
    ROUND(invoices.remaining,2) AS 'Остатък'
FROM (
    SELECT
		PartnersGroups.Name		AS parGroup,
        d.invoicenumber         AS invnum,
        d.ExternalInvoiceNumber AS toinvnum,
        d.DocumentType          AS dDocType,
        d.invoicedate           AS invdate,
        p.acct                  AS docnum,
        p.Opertype              AS pOperType,
        p.enddate               AS EndDate,
        oper.Note				AS operNote,
        partners.company        AS pName,
		
		DATEDIFF(DAY, p.enddate, GETDATE()) AS due_day,
        SUM(p.qtty * p.mode * p.sign * -1) AS remaining,
        SUM(CASE p.mode WHEN -1 THEN p.qtty ELSE 0 END) AS totalsum,
        SUM(CASE p.mode WHEN  1 THEN p.qtty ELSE 0 END) AS paidsum,
        MAX(CASE p.mode WHEN 1 THEN p.Date ELSE NULL END) AS paidDate
    FROM payments p
    LEFT JOIN documents d 
        ON d.acct = p.acct 
       AND d.opertype = p.opertype
    LEFT JOIN partners 
        ON partners.id = p.partnerId
	INNER JOIN PartnersGroups ON PartnersGroups.ID = Partners.GroupID
    INNER JOIN Operations AS oper ON oper.Acct = p.Acct and oper.OperType = p.OperType
    WHERE p.opertype IN (2, 16, 26, 27) and Partners.GroupID = 28
    GROUP BY 
		PartnersGroups.[Name],
        d.invoicenumber,
        d.ExternalInvoiceNumber,
        d.DocumentType,
        d.invoicedate,
        p.acct,
        p.Opertype,
        p.enddate,
		partners.Code,
        partners.company,
		oper.Note
    HAVING ABS(SUM(p.qtty * p.mode * p.sign * -1)) > 0.01 	
) invoices
ORDER BY invoices.parGroup, invoices.pName, invoices.invdate, invoices.due_day DESC