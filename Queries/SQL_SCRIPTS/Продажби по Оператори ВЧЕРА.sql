SELECT
    CAST(Oper.Date AS DATE) AS 'Дата', Us.Name AS 'Оператор', obj.Name AS 'Обект', COUNT(DISTINCT oper.Acct) AS 'Брой продажби', SUM(oper.qtty * oper.Sign * oper.PriceOut)*(-1) AS 'Сума'
FROM Operations as oper
Join Users as us ON Us.ID = Oper.operatorID
Join Objects as obj ON Obj.ID = Oper.ObjectID
--WHERE Oper.OperType = 2 and Oper.Date <= CAST(GETDATE() - 2 AS DATE)
WHERE Oper.OperType = 2 and Oper.Date = CAST(GETDATE() - 1 AS DATE) 
Group By Us.Name, Obj.Name, Oper.Date
Order By CAST(oper.Date AS DATE) DESC, obj.Name, Us.Name