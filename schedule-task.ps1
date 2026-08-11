# Registers an hourly Windows Task Scheduler job that runs the magenta-tracker
# sync (update.sh) through Git Bash, as the current user, when logged on.
# Re-runnable: -Force replaces any existing task of the same name.
$ErrorActionPreference = "Stop"

$proj     = "C:\Users\malka\magenta-tracker"
$taskName = "MagentaTracker"

# locate Git Bash from the git.exe on PATH  (...\Git\cmd\git.exe -> ...\Git\bin\bash.exe)
$gitExe = (Get-Command git -ErrorAction Stop).Source
$bash   = Join-Path (Split-Path (Split-Path $gitExe)) "bin\bash.exe"
if (-not (Test-Path $bash)) { throw "bash.exe not found at $bash" }

# run update.sh, appending stdout/stderr to sync.log (update.sh cd's to its own dir)
$cmd = "'/c/Users/malka/magenta-tracker/update.sh' >> '/c/Users/malka/magenta-tracker/sync.log' 2>&1"
$action = New-ScheduledTaskAction -Execute $bash -Argument "-lc `"$cmd`"" -WorkingDirectory $proj

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
Write-Host "  runs      : $bash -lc `"$cmd`""
Write-Host "  log       : $proj\sync.log"
Write-Host "Run it now without waiting:  Start-ScheduledTask -TaskName $taskName"
