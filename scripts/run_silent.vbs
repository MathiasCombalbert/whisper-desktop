Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
strCurDir = FSO.GetParentFolderName(strScriptDir)
If Not FSO.FileExists(strCurDir & "\config.json") Then
    strCurDir = strScriptDir
End If
WshShell.CurrentDirectory = strCurDir

' 1. Lancer l'executable autonome compile s'il existe
strExe = strCurDir & "\dist\WhisperDesktop\WhisperDesktop.exe"
If FSO.FileExists(strExe) Then
    WshShell.Run """" & strExe & """", 0, False
    WScript.Quit
End If

' 2. Sinon lancer via pythonw et src/app.py
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
