# Registers an hourly Windows Task Scheduler job that runs the magenta-tracker
# sync (update.sh) through Git Bash, as the current user, when logged on.
# Re-runnable: -Force replaces any existing task of the same name.
$ErrorActionPreference = "Stop"

$proj     = "C:\Users\malka\magenta-tracker"
$taskName = "MagentaTracker"

# locate Git Bash from the git.exe on PATH  (...\Git\cmd\git.exe -> ...\Git\bin\bash.exe)
# (run-hidden.vbs hardcodes this same path; the check here just fails fast if Git moved)
$gitExe = (Get-Command git -ErrorAction Stop).Source
$bash   = Join-Path (Split-Path (Split-Path $gitExe)) "bin\bash.exe"
if (-not (Test-Path $bash)) { throw "bash.exe not found at $bash" }

# Launch through wscript.exe + run-hidden.vbs rather than bash.exe directly:
# bash.exe is a console-subsystem program, so under an interactive logon Task
# Scheduler pops a visible console window every hour. wscript.exe is GUI-subsystem
# and the .vbs starts bash with SW_HIDE, so nothing is shown. The .vbs waits for
# bash to finish, so ExecutionTimeLimit / IgnoreNew / Last Run Result still work.
# //B = batch mode: never show a VBScript error dialog on an unattended run.
$vbs = Join-Path $proj "run-hidden.vbs"
if (-not (Test-Path $vbs)) { throw "run-hidden.vbs not found at $vbs" }
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "//B //Nologo `"$vbs`"" -WorkingDirectory $proj

# first run at the next top of the hour, then every hour
$next = (Get-Date -Minute 0 -Second 0 -Millisecond 0).AddHours(1)
$trigger = New-ScheduledTaskTrigger -Once -At $next `
             -RepetitionInterval (New-TimeSpan -Hours 1) `
             -RepetitionDuration  (New-TimeSpan -Days 3650)

# resilient settings: catch up missed runs, survive battery, don't overlap
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
             -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
             -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# run as the current user (needed for the gh keyring), non-elevated
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Registered '$taskName'."
Write-Host "  first run : $next  (then every hour)"
Write-Host "  runs      : wscript.exe //B //Nologo `"$vbs`"  (-> hidden $bash -lc update.sh)"
Write-Host "  log       : $proj\sync.log"
Write-Host "Run it now without waiting:  Start-ScheduledTask -TaskName $taskName"
