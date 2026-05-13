Set oShell = CreateObject("WScript.Shell")
Set oFS = CreateObject("Scripting.FileSystemObject")
strDir = oFS.GetParentFolderName(WScript.ScriptFullName)
oShell.Run "pythonw """ & strDir & "\jarvis.py""", 0, False
