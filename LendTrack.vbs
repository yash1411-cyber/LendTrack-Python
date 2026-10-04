' LendTrack development launcher — repo-relative (no hardcoded user paths).
Option Explicit
Dim fso, sh, root, pythonw, python, mainpy, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\pythonw.exe"
python = root & "\.venv\Scripts\python.exe"
mainpy = root & "\main.py"

If fso.FileExists(pythonw) Then
    sh.Run """" & pythonw & """ """ & mainpy & """", 0, False
ElseIf fso.FileExists(python) Then
    sh.Run """" & python & """ """ & mainpy & """", 1, False
Else
    MsgBox "LendTrack: .venv Python not found." & vbCrLf & _
           "Create/activate .venv and install dependencies first.", _
           vbCritical, "LendTrack"
End If
