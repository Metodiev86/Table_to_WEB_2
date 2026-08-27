;WITH Parameters AS
(
    SELECT
        CAST(:StartPeriod AS date) AS StartPeriod,
        CAST(:EndPeriod AS date) AS EndPeriod,

        DATEDIFF(
            DAY,
            :CoefficientStart,
            :CoefficientEnd
        ) AS ForecastDays,

        DATEDIFF(
            DAY,
            :StartPeriod,
            :EndPeriod
        ) AS PeriodDays
),
StoreBalance AS
(
    SELECT
        obj.ID AS ObjectID,
        obj.Name AS Обект,
        g.ID AS GoodID,
        g.Code AS Код,
        g.Name AS Артикул,
        gg.Name AS Група,
        g.Catalog1 AS Каталог1,
        g.Measure1 AS Мярка,
        g.Ratio AS Разфасовка,
        CASE
            WHEN g.Ratio < 1 THEN st.Qtty 
            ELSE st.Qtty / g.Ratio
        END AS Наличност,
        CASE
            WHEN g.Ratio < 1 THEN g.PriceIn 
            ELSE g.PriceIn * g.Ratio
        END AS Доставна
    FROM Store st
    INNER JOIN Goods g ON st.GoodID = g.ID
    INNER JOIN Objects obj ON st.ObjectID = obj.ID
    INNER JOIN GoodsGroups gg ON gg.ID = g.GroupID
    WHERE
        g.Deleted = 0
        AND g.Type = 0
		AND obj.ID in (4, 5, 10)
        AND (:warehouse = 'Всички' OR obj.Name = :warehouse)
        AND (
				gg.Code LIKE(
						SELECT code
						from GoodsGroups
						WHERE name = :gGroup
						) + '%')
		AND ((:ordered = 1 AND g.IsOnlyOrdered = 1)
		OR (:ordered = 0 AND g.IsOnlyOrdered = 0))
),
OperationsData AS
(
    SELECT
        oper.ObjectID,
        oper.GoodID,
        oper.OperType,
        CASE
            WHEN g.Ratio < 1 
				THEN oper.Qtty
				ELSE oper.Qtty / g.Ratio
        END AS Qty
    FROM Operations oper
    INNER JOIN Goods g ON g.ID = oper.GoodID
    INNER JOIN GoodsGroups gg ON gg.ID = g.GroupID
    CROSS JOIN Parameters p
    WHERE
        oper.Date BETWEEN p.StartPeriod AND p.EndPeriod
        AND oper.OperType IN (2, 8, 12, 19)
        AND g.Type = 0
        AND g.Deleted = 0
        AND (
--				gg.Code LIKE 'AAM%' 
--			OR 
				gg.Code LIKE(
						SELECT code
						from GoodsGroups
						WHERE name = :gGroup
						) + '%')
),
OperationsSummary AS
(
    SELECT
        ObjectID,
        GoodID,
        SUM(CASE WHEN OperType = 2 THEN Qty ELSE 0 END) AS Продадено,
        SUM(CASE WHEN OperType = 8 THEN Qty ELSE 0 END) AS Трансфер,
        SUM(CASE WHEN OperType = 12 THEN Qty ELSE 0 END) AS Заявено,
        SUM(CASE WHEN OperType = 19 THEN Qty ELSE 0 END) AS Поръчано
    FROM OperationsData
    GROUP BY
        ObjectID,
        GoodID
),
Summary AS
(
    SELECT
        sb.*,
        ISNULL(op.Продадено, 0) AS Продадено,
        ISNULL(op.Трансфер, 0) AS Трансфер,
        ISNULL(op.Заявено, 0) AS Заявено,
        ISNULL(op.Поръчано, 0) AS Поръчано
    FROM StoreBalance sb
    LEFT JOIN OperationsSummary op ON sb.ObjectID = op.ObjectID AND sb.GoodID = op.GoodID
),
Calculation AS
(
    SELECT
        s.*,
        p.PeriodDays,
        p.ForecastDays,
        CAST(
            (s.Продадено + s.Трансфер) / NULLIF(p.PeriodDays, 0)* 1.25
            AS decimal(18, 4)
        ) AS Среднодневно,
        (s.Наличност + s.Заявено - s.Поръчано
		) AS БрутноКоличество
    FROM Summary s
    CROSS JOIN Parameters p -- Добавен CROSS JOIN, за да са достъпни p.PeriodDays и p.ForecastDays
),
RequestCalculation AS
(
    SELECT
        *,
        -- Тук използваме директно ForecastDays, тъй като вече е селектирана в Calculation
        CASE WHEN Среднодневно >= 0.02
			THEN
				ROUND((Среднодневно * ForecastDays) - БрутноКоличество, 2)
			ELSE
				0
		END AS ЗаЗаявка
    FROM Calculation
)
SELECT
    Обект,
    Група,
    Код,
    Артикул,
    Каталог1,
    Мярка,
    Разфасовка,
    Наличност,
    Продадено,
    Трансфер,
    Заявено,
    Поръчано,
    Среднодневно,
    БрутноКоличество,
    ЗаЗаявка,
    CASE
        WHEN ЗаЗаявка > 0 
		THEN ЗаЗаявка * Доставна
        ELSE 0
    END AS ЦенаНаЗаявката
FROM RequestCalculation
WHERE
    :only_positive_request = 0
    OR ЗаЗаявка > 0
ORDER BY
    Група,
    Артикул
	
