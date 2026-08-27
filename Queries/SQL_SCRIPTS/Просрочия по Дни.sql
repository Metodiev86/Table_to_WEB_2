SELECT
    partners.company AS 'Партньор',
	
	ROUND(SUM(p.qtty * p.mode * p.sign * -1),2) AS 'Общо',

    ROUND(SUM(
        CASE 
            WHEN DATEDIFF(DAY, p.enddate, GETDATE()) <= 0
            THEN p.qtty * p.mode * p.sign * -1
            ELSE 0
        END
    ),2) AS 'Текущи',

    ROUND(SUM(
        CASE 
            WHEN DATEDIFF(DAY, p.enddate, GETDATE()) BETWEEN 1 AND 15
            THEN p.qtty * p.mode * p.sign * -1
            ELSE 0
        END
    ),2) AS 'До 15',

    ROUND(SUM(
        CASE 
            WHEN DATEDIFF(DAY, p.enddate, GETDATE()) BETWEEN 16 AND 30
            THEN p.qtty * p.mode * p.sign * -1
            ELSE 0
        END
    ),2) AS 'До 30',

    ROUND(SUM(
        CASE 
            WHEN DATEDIFF(DAY, p.enddate, GETDATE()) BETWEEN 31 AND 60
            THEN p.qtty * p.mode * p.sign * -1
            ELSE 0
        END
    ),2) AS 'До 60',

    ROUND(SUM(
        CASE 
            WHEN DATEDIFF(DAY, p.enddate, GETDATE()) > 60
            THEN p.qtty * p.mode * p.sign * -1
            ELSE 0
        END
    ),2) AS 'Над 60'

FROM payments p

LEFT JOIN documents d 
    ON d.acct = p.acct 
   AND d.opertype = p.opertype

LEFT JOIN partners 
    ON partners.id = p.partnerId

WHERE p.opertype IN (2,16,26,27) and Partners.Company <>''

GROUP BY partners.company

HAVING ABS(SUM(p.qtty * p.mode * p.sign * -1)) > 0.01

ORDER BY partners.company