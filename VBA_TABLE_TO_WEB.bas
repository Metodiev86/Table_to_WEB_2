
' Class module: CDataTableGenerator
Option Explicit

Private mTemplate As String

' =========================
' Публичен Интерфейс
' =========================

Public Sub Init(ByVal templatePath As String)
    mTemplate = ReadTextFile(templatePath)
End Sub

Public Sub Generate(lo As Object, _
                    ByVal InputFilePath As String, _
                    ByVal OutputPath As String)

    Dim html As String
    html = mTemplate

    Dim arr As Variant
    arr = lo.DataBodyRange.Value

    Dim dateCols As Object
    Set dateCols = DetectDateColumnsOnArray(arr)

    Dim numericCols As Object
    Set numericCols = DetectNumericColumnsOnArray(arr)

    Dim tableJson As String
    tableJson = TableToJsonFromArray(arr)

    Dim statsJson As String
    statsJson = CalculateDescriptiveStatsJson(arr, lo, dateCols, numericCols)

    Dim headersHtml As String
    headersHtml = BuildFilterHeaders(lo)

    Dim dateColsJson As String
    dateColsJson = CollectionToJsonArray(dateCols)

    Dim numericColsJson As String
    numericColsJson = CollectionToJsonArray(numericCols)

    Dim rowCount As Long
    rowCount = lo.DataBodyRange.Rows.Count

    ' ПРЕДУПРЕЖДЕНИЕ ЗА ГОЛЯМ БРОЙ ЗАПИСИ
    If rowCount > 20000 Then
        Dim msg As String
        msg = "Таблицата съдържа " & Format(rowCount, "#,##0") & " записа." & vbCrLf & vbCrLf & _
              "Генерирането на HTML може да отнеме време и файлът ще бъде тежък за браузъра." & vbCrLf & vbCrLf & _
              "Желаете ли да продължите?"
        If MsgBox(msg, vbYesNo + vbExclamation, "Внимание: Голям обем данни") = vbNo Then
            Exit Sub
        End If
    End If

    Dim colCount As Long
    colCount = lo.ListColumns.Count

    Dim inputFileNameWithExt As String
    inputFileNameWithExt = GetFileNameWithExtension(InputFilePath)

    Dim fileNameNoExt As String
    fileNameNoExt = GetFileNameWithoutExtension(InputFilePath)

    Dim nowStr As String
    nowStr = Format$(Now, " dd.mm.yyyy hh:nn:ss")

    html = Replace(html, "{{TABLE_DATA}}", tableJson)
    html = Replace(html, "{{DESCRIPTIVE_STATS}}", statsJson)
    html = Replace(html, "{{FILTER_HEADERS}}", headersHtml)
    html = Replace(html, "{{ROW_COUNT}}", CStr(rowCount))
    html = Replace(html, "{{COLUMN_COUNT}}", CStr(colCount))
    html = Replace(html, "{{FILE_NAME}}", fileNameNoExt)
    html = Replace(html, "{{INPUT_FILE_NAME_WITH_EXTENSION}}", inputFileNameWithExt)
    html = Replace(html, "{{DATE_TIME_NOW}}", nowStr)
    html = Replace(html, "{{DATE_COLUMNS}}", dateColsJson)
    html = Replace(html, "{{NUMERIC_COLUMNS}}", numericColsJson)

    WriteTextFileUTF8 OutputPath, html
End Sub

' =========================
' Четене/Писане във Файл
' =========================

Private Function ReadTextFile(ByVal FilePath As String) As String
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")

    With stream
        .Type = 2 ' text stream
        .Charset = "utf-8" ' specify UTF-8 encoding
        .Open
        .LoadFromFile FilePath
        ReadTextFile = stream.ReadText(-1) ' Read all text
        .Close
    End With
End Function

Private Sub WriteTextFileUTF8(ByVal FilePath As String, ByVal Content As String)
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")

    With stream
        .Type = 2 ' text
        .Charset = "utf-8"
        .Open
        .WriteText Content
        .SaveToFile FilePath, 2 ' overwrite
        .Close
    End With
End Sub

' =========================
' Помощни имена на файлове
' =========================

Private Function GetFileNameWithExtension(ByVal FullPath As String) As String
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    GetFileNameWithExtension = fso.GetFileName(FullPath)
End Function

Private Function GetFileNameWithoutExtension(ByVal FullPath As String) As String
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    GetFileNameWithoutExtension = fso.GetBaseName(FullPath)
End Function

' =========================
' Детекция на Дати (Python-Подобна Логика)
' =========================

Private Function DetectDateColumnsOnArray(ByRef arr As Variant) As Object ' Return Object (Collection)
    Dim result As Object
    Set result = CreateObject("Scripting.Dictionary") ' Use Dictionary as a collection substitute for safer Late Binding

    Dim rowsCount As Long
    Dim colsCount As Long
    rowsCount = UBound(arr, 1)
    colsCount = UBound(arr, 2)

    Dim formats As Variant
    formats = Array( _
        "%d.%m.%Y", _
        "%d.%m.%Y %H:%M:%S", _
        "%Y-%m-%d", _
        "%Y-%m-%d %H:%M:%S", _
        "%d/%m/%Y" _
    )

    Dim col As Long
    For col = 1 To colsCount

        Dim bestRatio As Double
        bestRatio = 0

        Dim bestParsed() As Variant
        Dim hasBest As Boolean
        hasBest = False

        Dim fmtIndex As Long
        For fmtIndex = LBound(formats) To UBound(formats)

            Dim tmpParsed() As Variant
            ReDim tmpParsed(1 To rowsCount)

            Dim validCount As Long
            validCount = 0
            Dim nonEmptyCount As Long
            nonEmptyCount = 0

            Dim r As Long
            For r = 1 To rowsCount
                Dim v As Variant
                v = arr(r, col)

                If IsError(v) Then
                    tmpParsed(r) = ""
                ElseIf IsEmpty(v) Or IsNull(v) Or Trim(CStr(v)) = "" Then
                    tmpParsed(r) = v
                Else
                    nonEmptyCount = nonEmptyCount + 1
                    If VarType(v) = vbDate Then
                        tmpParsed(r) = Format$(v, "yyyy-mm-dd")
                        validCount = validCount + 1
                    Else
                        Dim cleanedV As String
                        cleanedV = NormalizeDateString(CStr(v))
                        
                        Dim d As Date
                        If TryParseDateByFormat(cleanedV, CStr(formats(fmtIndex)), d) Then
                            tmpParsed(r) = Format$(d, "yyyy-mm-dd")
                            validCount = validCount + 1
                        Else
                            tmpParsed(r) = v
                        End If
                    End If
                End If
            Next r

            Dim ratio As Double
            If nonEmptyCount > 0 Then
                ratio = validCount / nonEmptyCount
            Else
                ratio = 0
            End If

            If ratio > bestRatio Then
                bestRatio = ratio
                bestParsed = tmpParsed
                hasBest = True
            End If
        Next fmtIndex

        If hasBest Then
            If bestRatio >= 0.9 Then
                Dim rr As Long
                For rr = 1 To rowsCount
                    arr(rr, col) = bestParsed(rr)
                Next rr
                result.Add col - 1, col - 1 ' Add to dictionary as a collection
            End If
        End If
    Next col

    Set DetectDateColumnsOnArray = result
End Function

Private Function NormalizeDateString(ByVal s As String) As String
    s = LCase$(Trim$(s))
    
    ' 1. Премахване на паразитни символи (г., год., г)
    s = Replace(s, " год.", "")
    s = Replace(s, " год", "")
    s = Replace(s, " г.", "")
    s = Replace(s, " г", "")
    
    ' 2. Преобразуване на български месеци
    ' Пълни имена
    s = Replace(s, "януари", "01")
    s = Replace(s, "февруари", "02")
    s = Replace(s, "март", "03")
    s = Replace(s, "април", "04")
    s = Replace(s, "май", "05")
    s = Replace(s, "юни", "06")
    s = Replace(s, "юли", "07")
    s = Replace(s, "август", "08")
    s = Replace(s, "септември", "09")
    s = Replace(s, "октомври", "10")
    s = Replace(s, "ноември", "11")
    s = Replace(s, "декември", "12")
    
    ' Съкращения (ако има точки след тях)
    s = Replace(s, "ян.", "01")
    s = Replace(s, "февр.", "02")
    s = Replace(s, "март.", "03")
    s = Replace(s, "апр.", "04")
    s = Replace(s, "май.", "05")
    s = Replace(s, "юни.", "06")
    s = Replace(s, "юли.", "07")
    s = Replace(s, "авг.", "08")
    s = Replace(s, "септ.", "09")
    s = Replace(s, "окт.", "10")
    s = Replace(s, "ноем.", "11")
    s = Replace(s, "дек.", "12")
    
    ' 3. Почистване на двойни интервали
    Do While InStr(s, "  ") > 0
        s = Replace(s, "  ", " ")
    Loop
    
    ' 4. Ако след замяната на месеца имаме "01 2024", добавяме точки за формат "01.01.2024"
    ' Това е само ако TryParseDateByFormat очаква точки
    s = Replace(s, " ", ".")
    
    NormalizeDateString = s
End Function

Private Function TryParseDateByFormat(ByVal s As String, _
                                      ByVal fmt As String, _
                                      ByRef outDate As Date) As Boolean
    On Error GoTo FailHandler

    s = Trim$(s)
    If s = "" Then GoTo FailHandler

    Dim datePart As String
    Dim timePart As String
    Dim parts() As String
    Dim d As Long, m As Long, y As Long
    Dim hh As Long, nn As Long, ss As Long

    Select Case fmt

        Case "%d.%m.%Y"
            parts = Split(s, ".")
            If UBound(parts) <> 2 Then GoTo FailHandler
            d = CLng(parts(0))
            m = CLng(parts(1))
            y = CLng(parts(2))
            outDate = DateSerial(y, m, d)
            TryParseDateByFormat = True
            Exit Function

        Case "%d.%m.%Y %H:%M:%S"
            parts = Split(s, " ")
            If UBound(parts) <> 1 Then GoTo FailHandler
            datePart = parts(0)
            timePart = parts(1)

            Dim dp() As String
            dp = Split(datePart, ".")
            If UBound(dp) <> 2 Then GoTo FailHandler
            d = CLng(dp(0))
            m = CLng(dp(1))
            y = CLng(dp(2))

            Dim tp() As String
            tp = Split(timePart, ":")
            If UBound(tp) <> 2 Then GoTo FailHandler
            hh = CLng(tp(0))
            nn = CLng(tp(1))
            ss = CLng(tp(2))

            outDate = DateSerial(y, m, d) + TimeSerial(hh, nn, ss)
            TryParseDateByFormat = True
            Exit Function

        Case "%Y-%m-%d"
            parts = Split(s, "-")
            If UBound(parts) <> 2 Then GoTo FailHandler
            y = CLng(parts(0))
            m = CLng(parts(1))
            d = CLng(parts(2))
            outDate = DateSerial(y, m, d)
            TryParseDateByFormat = True
            Exit Function

        Case "%Y-%m-%d %H:%M:%S"
            parts = Split(s, " ")
            If UBound(parts) <> 1 Then GoTo FailHandler
            datePart = parts(0)
            timePart = parts(1)

            Dim dp2() As String
            dp2 = Split(datePart, "-")
            If UBound(dp2) <> 2 Then GoTo FailHandler
            y = CLng(dp2(0))
            m = CLng(dp2(1))
            d = CLng(dp2(2))

            Dim tp2() As String
            tp2 = Split(timePart, ":")
            If UBound(tp2) <> 2 Then GoTo FailHandler
            hh = CLng(tp2(0))
            nn = CLng(tp2(1))
            ss = CLng(tp2(2))

            outDate = DateSerial(y, m, d) + TimeSerial(hh, nn, ss)
            TryParseDateByFormat = True
            Exit Function

        Case "%d/%m/%Y"
            parts = Split(s, "/")
            If UBound(parts) <> 2 Then GoTo FailHandler
            d = CLng(parts(0))
            m = CLng(parts(1))
            y = CLng(parts(2))
            outDate = DateSerial(y, m, d)
            TryParseDateByFormat = True
            Exit Function

        Case Else
            GoTo FailHandler
    End Select

FailHandler:
    TryParseDateByFormat = False
End Function

' =========================
' Детекция на Числови Колони
' =========================

Private Function DetectNumericColumnsOnArray(ByRef arr As Variant) As Object
    Dim result As Object
    Set result = CreateObject("Scripting.Dictionary")

    Dim rowsCount As Long
    Dim colsCount As Long
    rowsCount = UBound(arr, 1)
    colsCount = UBound(arr, 2)

    Dim col As Long
    For col = 1 To colsCount

        Dim validCount As Long
        validCount = 0
        Dim totalCount As Long
        totalCount = 0

        Dim r As Long
        For r = 1 To rowsCount
            Dim v As Variant
            v = arr(r, col)

            If IsError(v) Then
                ' Treat error as non-numeric
            ElseIf Not (IsEmpty(v) Or IsNull(v) Or Trim(CStr(v)) = "") Then
                totalCount = totalCount + 1
                
                ' Ако вече е число
                If IsNumeric(v) Then
                    validCount = validCount + 1
                Else
                    ' Опитваме се да го "почистим" (както в Python)
                    Dim cleaned As String
                    cleaned = RegexCleanNumeric(CStr(v))
                    If cleaned <> "" Then
                        If IsNumeric(cleaned) Then
                            validCount = validCount + 1
                        End If
                    End If
                End If
            End If
        Next r

        ' Ако >= 90% от непразните клетки са числови
        If totalCount > 0 Then
            If (validCount / totalCount) >= 0.9 Then
                result.Add col - 1, col - 1 ' zero-based index
            End If
        End If
    Next col

    Set DetectNumericColumnsOnArray = result
End Function

Private Function RegexCleanNumeric(ByVal s As String) As String
    Static regEx As Object
    If regEx Is Nothing Then
        Set regEx = CreateObject("VBScript.RegExp")
        regEx.Global = True
        ' Пазим само цифри, точка и минус
        regEx.Pattern = "[^\d.-]"
    End If
    RegexCleanNumeric = regEx.Replace(s, "")
End Function

' =========================
' Описателна статистика
' =========================

Private Function CalculateDescriptiveStatsJson(ByRef arr As Variant, lo As Object, dateCols As Object, numericCols As Object) As String
    Dim rowsCount As Long
    Dim colsCount As Long
    rowsCount = UBound(arr, 1)
    colsCount = UBound(arr, 2)

    Dim json As String
    json = "{"

    Dim col As Long
    For col = 1 To colsCount
        Dim colName As String
        colName = lo.ListColumns(col).Name
        
        Dim isNum As Boolean: isNum = False
        Dim isDate As Boolean: isDate = False
        
        ' Проверка на типа чрез речника
        If numericCols.Exists(col - 1) Then isNum = True
        If Not isNum Then
            If dateCols.Exists(col - 1) Then isDate = True
        End If

        Dim total As Long: total = rowsCount
        Dim emptyCount As Long: emptyCount = 0
        Dim dictFreq As Object: Set dictFreq = CreateObject("Scripting.Dictionary")
        
        ' За числови
        Dim maxVal As Double: maxVal = -1E+308
        Dim minVal As Double: minVal = 1E+308
        Dim sumVal As Double: sumVal = 0
        Dim countNum As Long: countNum = 0
        Dim positives As Long: positives = 0
        Dim negatives As Long: negatives = 0
        Dim zeros As Long: zeros = 0
        
        ' За дати
        Dim maxDate As String: maxDate = ""
        Dim minDate As String: minDate = ""

        Dim r As Long
        For r = 1 To rowsCount
            Dim v As Variant
            v = arr(r, col)
            
            Dim valStr As String
            Dim isThisEmpty As Boolean
            isThisEmpty = False

            If IsError(v) Then
                emptyCount = emptyCount + 1
                valStr = "[Error]"
                isThisEmpty = True
            ElseIf IsEmpty(v) Or IsNull(v) Or Trim(CStr(v)) = "" Then
                emptyCount = emptyCount + 1
                valStr = ""
                isThisEmpty = True
            Else
                valStr = CStr(v)
            End If
            
            ' Frequencies (only non-empty values for unique count if we want to be strict)
            ' But we need all frequencies for the frequency table. 
            ' We'll count unique values later from the dictionary keys excluding empty string.
            If dictFreq.Exists(valStr) Then
                dictFreq(valStr) = dictFreq(valStr) + 1
            Else
                dictFreq.Add valStr, 1
            End If
            
            If isNum And Not isThisEmpty Then
                Dim n As Double
                n = Val(RegexCleanNumeric(valStr))
                If n > maxVal Then maxVal = n
                If n < minVal Then minVal = n
                sumVal = sumVal + n
                countNum = countNum + 1
                If n > 0 Then positives = positives + 1 Else If n < 0 Then negatives = negatives + 1 Else zeros = zeros + 1
            ElseIf isDate And Not isThisEmpty Then
                If minDate = "" Or valStr < minDate Then minDate = valStr
                If maxDate = "" Or valStr > maxDate Then maxDate = valStr
            End If
        Next r

        ' Build JSON for this column
        ' Unique count: keys minus empty string if it exists
        Dim uniqueCount As Long
        uniqueCount = dictFreq.Count
        If dictFreq.Exists("") Then uniqueCount = uniqueCount - 1
        
        json = json & """" & EscapeJsonString(colName) & """: {"
        json = json & """total"": " & total & ","
        json = json & """unique"": " & uniqueCount & ","
        json = json & """empty"": " & emptyCount & ","
        
        If isNum Then
            json = json & """type"": ""numeric"","
            If countNum > 0 Then
                json = json & """max"": " & Replace(CStr(maxVal), ",", ".") & ","
                json = json & """min"": " & Replace(CStr(minVal), ",", ".") & ","
                json = json & """avg"": " & Replace(CStr(sumVal / countNum), ",", ".") & ","
                json = json & """positives"": " & positives & ","
                json = json & """negatives"": " & negatives & ","
                json = json & """zeros"": " & zeros & ","
            Else
                json = json & """max"": null, ""min"": null, ""avg"": null, ""positives"": 0, ""negatives"": 0, ""zeros"": 0,"
            End If
        ElseIf isDate Then
            json = json & """type"": ""date"","
            json = json & """max"": " & IIf(maxDate <> "", """" & maxDate & """", "null") & ","
            json = json & """min"": " & IIf(minDate <> "", """" & minDate & """", "null") & ","
        Else
            json = json & """type"": ""text"","
        End If
        
        json = json & """frequencies"": " & DictionaryToJson(dictFreq)
        json = json & "}"
        
        If col < colsCount Then json = json & ","
    Next col

    json = json & "}"
    CalculateDescriptiveStatsJson = json
End Function

Private Function DictionaryToJson(dict As Object) As String
    Dim json As String
    json = "{"
    
    Dim keys As Variant
    keys = dict.keys
    
    Dim i As Long
    For i = LBound(keys) To UBound(keys)
        Dim k As String
        k = EscapeJsonString(CStr(keys(i)))
        json = json & """" & k & """: " & dict(keys(i))
        If i < UBound(keys) Then json = json & ","
    Next i
    
    json = json & "}"
    DictionaryToJson = json
End Function

' =========================
' JSON сериализация
' =========================

Private Function TableToJsonFromArray(ByRef arr As Variant) As String
    Dim rowsCount As Long
    Dim colsCount As Long
    rowsCount = UBound(arr, 1)
    colsCount = UBound(arr, 2)

    Dim json As String
    json = "["

    Dim r As Long, c As Long
    For r = 1 To rowsCount
        json = json & "["
        For c = 1 To colsCount
            Dim v As Variant
            v = arr(r, c)

            Dim s As String
            If IsError(v) Then
                s = "[Error]"
            ElseIf IsEmpty(v) Or IsNull(v) Then
                s = ""
            Else
                s = CStr(v)
            End If

            s = EscapeJsonString(s)
            json = json & """" & s & """"

            If c < colsCount Then
                json = json & ","
            End If
        Next c
        json = json & "]"
        If r < rowsCount Then
            json = json & ","
        End If
    Next r

    json = json & "]"
    TableToJsonFromArray = json
End Function

Private Function CollectionToJsonArray(col As Object) As String
    Dim json As String
    json = "["

    Dim keys As Variant
    keys = col.keys
    
    Dim i As Long
    For i = LBound(keys) To UBound(keys)
        json = json & CStr(keys(i))
        If i < UBound(keys) Then
            json = json & ","
        End If
    Next i

    json = json & "]"
    CollectionToJsonArray = json
End Function

Private Function EscapeJsonString(ByVal s As String) As String
    s = Replace(s, "\", "\\")
    s = Replace(s, """", "\""")
    s = Replace(s, vbCrLf, "\n")
    s = Replace(s, vbCr, "\n")
    s = Replace(s, vbLf, "\n")
    EscapeJsonString = s
End Function

' =========================
' FILTER_HEADERS
' =========================

Private Function BuildFilterHeaders(lo As Object) As String
    Dim res As String
    Dim i As Long

    For i = 1 To lo.ListColumns.Count
        Dim headerText As String
        headerText = lo.ListColumns(i).Name
        headerText = EscapeHtml(headerText)
        res = res & "<th>" & headerText & "</th>" & vbCrLf
    Next i

    BuildFilterHeaders = res
End Function

Private Function EscapeHtml(ByVal s As String) As String
    s = Replace(s, "&", "&amp;")
    s = Replace(s, "<", "&lt;")
    s = Replace(s, ">", "&gt;")
    EscapeHtml = s
End Function

Public Sub GenerateFromActiveTable()

    ' Проверка дали има поне една таблица в активния лист
    If ActiveSheet.ListObjects.Count = 0 Then
        MsgBox "Няма таблица (ListObject) в активния лист.", vbExclamation, "Грешка"
        Exit Sub
    End If

    Dim lo As Object ' Use Object for Late Binding
    Set lo = ActiveSheet.ListObjects(1)

    ' Име на таблицата
    Dim tableName As String
    tableName = lo.Name

    ' Папката, в която се намира активният Excel файл
    Dim outputFolder As String
    Dim fullPath As String
    fullPath = ActiveWorkbook.FullName
    
    If InStrRev(fullPath, "\") > 0 Then
        outputFolder = Left(fullPath, InStrRev(fullPath, "\"))
    Else
        ' Ако файлът още не е записан - Десктоп
        outputFolder = CreateObject("WScript.Shell").SpecialFolders("Desktop") & "\"
    End If

    ' Генериране на динамично име на HTML файла
    Dim outputFile As String
    outputFile = outputFolder & tableName & ".html"

    ' Път към темплейта
    Dim templatePath As String
    templatePath = ThisWorkbook.Path & "\Templates\template_Table_to_HTML.html"

    ' Четем темплейта директно в модулната променлива mTemplate
    mTemplate = ReadTextFile(templatePath)
    
    ' Стартираме генерирането
    Generate lo, fullPath, outputFile

    MsgBox "Готово! Файлът е създаден:" & vbCrLf & outputFile

End Sub



