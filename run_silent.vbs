Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strCurDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strCurDir

strPythonw = "pythonw.exe"
If FSO.FileExists("C:\Python313\pythonw.exe") Then
    strPythonw = "C:\Python313\pythonw.exe"
ElseIf FSO.FileExists(WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe")) Then
    strPythonw = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe")
End If

strAppPath = strCurDir & "\src\app.py"
If Not FSO.FileExists(strAppPath) Then
    strAppPath = strCurDir & "\app.py"
End If

WshShell.Run """" & strPythonw & """ """ & strAppPath & """", 0, False
