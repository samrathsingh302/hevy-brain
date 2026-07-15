' run_hidden.vbs - launch any command with NO console window.
' powershell.exe -WindowStyle Hidden still flashes a console/Windows Terminal tab
' (the console is created before PowerShell parses the flag); wscript.exe is a GUI
' app, so launching through this wrapper never creates one. Used by the scheduled
' tasks register_task.ps1 registers.
' Usage: wscript.exe run_hidden.vbs <exe> [args...]
Dim a, i, p, s
Set a = WScript.Arguments
s = ""
For i = 0 To a.Count - 1
    p = a(i)
    If InStr(p, " ") > 0 Then p = Chr(34) & p & Chr(34)
    s = s & p & " "
Next
' Wait for the child (True): wscript then lives as long as the real work, so the
' task's MultipleInstances/ExecutionTimeLimit settings still apply to it.
If Len(s) > 0 Then CreateObject("WScript.Shell").Run Trim(s), 0, True
