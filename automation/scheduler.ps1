# eBay Return Analysis (RA) - monthly scheduler registration.
#
#   .\scheduler.ps1                 register (or inspect) the monthly task
#   .\scheduler.ps1 -Mode status    show the current registration and next run
#   .\scheduler.ps1 -Mode repair    force the task back to the intended definition
#   .\scheduler.ps1 -Mode runnow    trigger a run immediately
#   .\scheduler.ps1 -Mode remove    unregister the task
#
# Runs on the 1st of every month at 07:00 local time. The run itself works out
# which month to report on from the date it starts, so no date ever needs to be
# edited here or anywhere else.
#
# NO SECOND SCHEDULER. Registration inspects the existing task first and
# repairs it in place rather than adding another entry, and it reports any
# OTHER scheduled task that points at this same automation. The separate ERA
# Return Analysis stream is a different developer's and is never touched.
#
# ELEVATION. This shell runs with a filtered token, so a task requiring
# HighestAvailable cannot be registered from here. The task is registered with
# LeastPrivilege / InteractiveToken, which is sufficient for this workload, and
# a full-privilege XML is written alongside it for an administrator to import
# if the business later needs it. Deliberate, and reported.
#
# ENVIRONMENT. The task runs as your user account and inherits your USER-level
# environment. WLP_SOURCE_DB_URL (ledsone, read-only source) and DATABASE_URL
# (order_management_copy, the ph_task publish target) must both be set at USER
# level or the run aborts in preflight without touching anything.
#
# ASCII only on purpose: a BOM-less UTF-8 .ps1 containing an em dash fails to
# parse under Windows PowerShell 5.1.

[CmdletBinding()]
param(
    [ValidateSet('register', 'status', 'repair', 'runnow', 'remove')]
    [string]$Mode = 'register',
    [string]$TaskName = 'RA_Monthly_Return_Analysis',
    [int]$Day = 1,
    [string]$Time = '07:00'
)

$ErrorActionPreference = 'Stop'

$AutomationDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot   = Split-Path -Parent $AutomationDir
$RunScript     = Join-Path $AutomationDir 'run.py'
$XmlOut        = Join-Path $AutomationDir ("$TaskName" + '_FULL_PRIVILEGE.xml')

if (-not (Test-Path $RunScript)) { throw "run.py not found at $RunScript" }

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCmd) {
    throw "python was not found on PATH. Install Python or add it to PATH before registering the task."
}
$Python = $pythonCmd.Source

$hour   = [int]$Time.Split(':')[0]
$minute = [int]$Time.Split(':')[1]

# Next occurrence of the configured day at the configured time.
$now  = Get-Date
$next = Get-Date -Day $Day -Hour $hour -Minute $minute -Second 0 -Millisecond 0
if ($next -le $now) { $next = $next.AddMonths(1) }
$startBoundary = $next.ToString('yyyy-MM-ddTHH:mm:ss')

$user = "$env:USERDOMAIN\$env:USERNAME"

function New-TaskXml {
    param([string]$RunLevel)
@"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>eBay Return Analysis (RA) - monthly regeneration, independent validation against the live database, and publication to tech_team_outputs.ph_task under project_code RA. The reporting month is the previous calendar month, calculated from the run date. Read-only against ledsone; the separate ERA stream is not touched.</Description>
    <URI>\$TaskName</URI>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth><Day>$Day</Day></DaysOfMonth>
        <Months>
          <January /><February /><March /><April /><May /><June />
          <July /><August /><September /><October /><November /><December />
        </Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$user</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>$RunLevel</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT30M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$Python</Command>
      <Arguments>"$RunScript"</Arguments>
      <WorkingDirectory>$AutomationDir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@
}

function Show-Task {
    param([string]$Name)
    $t = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($null -eq $t) {
        Write-Host "  task '$Name' is NOT registered"
        return $false
    }
    $info = Get-ScheduledTaskInfo -TaskName $Name
    Write-Host "  TaskName      : $($t.TaskName)"
    Write-Host "  TaskPath      : $($t.TaskPath)"
    Write-Host "  State         : $($t.State)"
    Write-Host "  RunLevel      : $($t.Principal.RunLevel)"
    Write-Host "  LogonType     : $($t.Principal.LogonType)"
    Write-Host "  UserId        : $($t.Principal.UserId)"
    foreach ($a in $t.Actions) {
        Write-Host "  Action        : $($a.Execute) $($a.Arguments)"
    }
    Write-Host "  Next run      : $($info.NextRunTime)"
    Write-Host "  Last run      : $($info.LastRunTime)"
    Write-Host "  Last result   : $($info.LastTaskResult)  (0 = success)"

    $summary = Join-Path $ProjectRoot 'logs\last_run_summary.json'
    if (Test-Path $summary) {
        $s = Get-Content $summary -Raw | ConvertFrom-Json
        Write-Host "  Last pipeline : $($s.status) in $($s.duration_seconds)s"
        Write-Host "                  execution date $($s.execution_date), reporting month $($s.reporting_month)"
        Write-Host "                  last month $($s.last_month_period) | last year $($s.last_year_period)"
        Write-Host "                  source rows $($s.source_row_count) | generated rows $($s.generated_row_count)"
        Write-Host "                  validation $($s.validation_result) | publish $($s.publish_result)"
    }
    $notice = Join-Path $ProjectRoot 'logs\FAILURE_NOTICE.txt'
    if (Test-Path $notice) {
        Write-Warning "FAILURE NOTICE present:"
        Get-Content $notice | ForEach-Object { Write-Host "    $_" }
    }
    return $true
}

function Find-OtherTasks {
    param([string]$Name)
    # Windows enforces unique task names per folder, so a true duplicate cannot
    # exist. What CAN exist is another task pointing at this same automation -
    # report those rather than assume none.
    $all = Get-ScheduledTask -ErrorAction SilentlyContinue
    $hits = @()
    foreach ($t in $all) {
        if ($t.TaskName -eq $Name) { continue }
        foreach ($a in $t.Actions) {
            if ($null -ne $a.Arguments -and $a.Arguments -like "*eBay_Return_Analysis*run.py*") {
                $hits += $t.TaskName
            }
        }
    }
    return $hits
}

Write-Host ""
Write-Host "eBay Return Analysis (RA) - monthly scheduler"
Write-Host "  task name  : $TaskName"
Write-Host "  schedule   : day $Day of every month at $Time local ($((Get-TimeZone).Id))"
Write-Host "  action     : $Python `"$RunScript`""
Write-Host "  next start : $startBoundary"
Write-Host "  reports    : the previous calendar month, worked out at run time"
Write-Host ""

if ($Mode -eq 'status') {
    Write-Host "Current registration:"
    $null = Show-Task -Name $TaskName
    $others = Find-OtherTasks -Name $TaskName
    Write-Host ""
    if ($others.Count -gt 0) {
        Write-Host "  WARNING other tasks also invoke this automation: $($others -join ', ')"
    } else {
        Write-Host "  no other scheduled task invokes this automation"
    }
    exit 0
}

if ($Mode -eq 'runnow') {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $existing) { throw "task '$TaskName' is not registered" }
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "  triggered '$TaskName'"
    exit 0
}

if ($Mode -eq 'remove') {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $existing) {
        Write-Host "  nothing to remove - '$TaskName' is not registered"
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  unregistered '$TaskName'"
    exit 0
}

# ---------------------------------------------------------------- register / repair
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($null -ne $existing -and $Mode -eq 'register') {
    Write-Host "  task '$TaskName' ALREADY EXISTS - inspecting instead of creating a duplicate"
    Write-Host ""
    $null = Show-Task -Name $TaskName

    $needsRepair = $false
    $reasons = @()

    $actionOk = $false
    foreach ($a in $existing.Actions) {
        if ($a.Arguments -like "*run.py*" -and $a.Execute -like "*python*") { $actionOk = $true }
    }
    if (-not $actionOk) { $needsRepair = $true; $reasons += 'action does not invoke run.py' }

    $trigger = $existing.Triggers | Select-Object -First 1
    if ($null -eq $trigger) { $needsRepair = $true; $reasons += 'no trigger' }

    if ($existing.State -eq 'Disabled') { $needsRepair = $true; $reasons += 'task is disabled' }

    Write-Host ""
    if ($needsRepair) {
        Write-Host "  REPAIR REQUIRED: $($reasons -join '; ')"
        Write-Host "  re-run with -Mode repair to correct it in place"
        exit 2
    }
    Write-Host "  registration is healthy - nothing to do"
    $others = Find-OtherTasks -Name $TaskName
    if ($others.Count -gt 0) {
        Write-Host "  WARNING other tasks also invoke this automation: $($others -join ', ')"
    }
    exit 0
}

$xmlLeast = New-TaskXml -RunLevel 'LeastPrivilege'
$xmlFull  = New-TaskXml -RunLevel 'HighestAvailable'

# The full-privilege definition is written for an administrator to import.
Set-Content -Path $XmlOut -Value $xmlFull -Encoding Unicode
Write-Host "  full-privilege XML written to: $XmlOut"
Write-Host "    apply from an ELEVATED prompt with:"
Write-Host "      schtasks /Create /TN `"$TaskName`" /XML `"$XmlOut`" /F"
Write-Host ""

if ($null -ne $existing) {
    Write-Host "  repairing existing task in place (no duplicate is created)"
}

$null = Register-ScheduledTask -TaskName $TaskName -Xml $xmlLeast -Force
Write-Host "  registered '$TaskName' (LeastPrivilege / InteractiveToken)"
Write-Host ""
Write-Host "Registration now reads:"
$null = Show-Task -Name $TaskName

$others = Find-OtherTasks -Name $TaskName
Write-Host ""
if ($others.Count -gt 0) {
    Write-Host "  WARNING other tasks also invoke this automation: $($others -join ', ')"
} else {
    Write-Host "  no other scheduled task invokes this automation"
}
Write-Host ""
Write-Host "Verify readiness at any time with:  python run.py --preflight"
Write-Host ""
