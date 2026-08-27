SELECT Oper.Date As "Дата", Us.Name As 'Оператор', COUNT(DISTINCT oper.Acct) As 'Брой продажби', SUM(oper.qtty * oper.Sign * oper.PriceOut)*(-1) As 'Сума',  obj.Name As 'Обект'
FROM Operations as oper
Join Users as us ON Us.ID = Oper.operatorID
Join Objects as obj ON Obj.ID = Oper.ObjectID
WHERE Oper.OperType = 2 
Group By Us.Name, Obj.Name, Oper.Date
Order By oper.Date DESC, obj.Name, Us.Name