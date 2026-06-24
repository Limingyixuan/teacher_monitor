param(
    [string]$Time = "08:30",
    [string]$TaskName = "保定初高中事业编招聘监控"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ProjectDir "run_monitor.ps1"
$PowerShell = (Get-Command powershell.exe).Source

$Action = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "每天检查保定地区初高中事业编教师招聘公告" `
    -Force

Write-Host "任务已创建：$TaskName（每天 $Time）"
