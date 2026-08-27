' run-hidden.vbs -- launch the hourly magenta-tracker sync with NO console window.
'
' Why: Git's bin\bash.exe is a console-subsystem program, so when Task Scheduler
' runs it under an interactive logon Windows pops a visible console for ~5s every
' hour. wscript.exe is GUI-subsystem, and WshShell.Run with window style 0 starts
' the child with SW_HIDE, so nothing is shown. Output still goes to sync.log via
' the redirect inside the bash command.
'
' Run synchronously (True) so Task Scheduler still enforces the 30-min execution
' limit and the no-overlap policy, and sees bash's real exit code.
Set sh = CreateObject("WScript.Shell")
bash = """C:\Program Files\Git\bin\bash.exe"""
args = "-lc ""'/c/Users/malka/magenta-tracker/update.sh' >> '/c/Users/malka/magenta-tracker/sync.log' 2>&1"""
rc = sh.Run(bash & " " & args, 0, True)
WScript.Quit rc
