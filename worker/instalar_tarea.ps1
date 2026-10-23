<#
Registra la tarea programada "Better Canvas" en el Programador de tareas de
Windows: corre el trabajador (python -m worker.run) cada 2 horas y al
iniciar sesion, recuperando la corrida si el equipo estaba apagado o sin
red. No requiere privilegios de administrador: queda registrada para el
usuario actual.

Uso: desde PowerShell, parado en cualquier carpeta:
  .\instalar_tarea.ps1

Para desinstalarla:
  Unregister-ScheduledTask -TaskName "Better Canvas"
#>

$ErrorActionPreference = "Stop"

$nombreTarea = "Better Canvas"
$repo = Split-Path -Parent $PSScriptRoot

# El launcher "py" resuelve el Python instalado para todo el sistema, no el
# primero que encuentre en el PATH: si esta sesion de PowerShell tiene un
# venv activado, "Get-Command pythonw" devolveria el pythonw de ese venv (que
# no tiene las dependencias del trabajador) en vez del real.
$pythonExe = & py -3 -c "import sys; print(sys.executable)"
$pythonw = Join-Path (Split-Path -Parent $pythonExe) "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    throw "No encuentro pythonw.exe junto a $pythonExe"
}

$accion = New-ScheduledTaskAction -Execute $pythonw -Argument "-m worker.run" `
    -WorkingDirectory $repo

$disparadorInicio = New-ScheduledTaskTrigger -AtLogOn

# Sin -RepetitionDuration, -Once + -RepetitionInterval repite
# indefinidamente (Windows 10/11); con -RepetitionDuration
# ([TimeSpan]::MaxValue) Register-ScheduledTask lo rechaza
# ("value incorrectly formatted or out of range").
$disparadorPeriodico = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 2)

$config = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

# -Force reemplaza la tarea si ya existe, sin un paso previo de
# desregistrarla: si el registro nuevo fallara, la tarea anterior (si
# funcionaba) sigue en pie en vez de quedar borrada.
Register-ScheduledTask -TaskName $nombreTarea `
    -Action $accion `
    -Trigger @($disparadorInicio, $disparadorPeriodico) `
    -Settings $config `
    -Principal $principal `
    -Force | Out-Null

Write-Host "Tarea '$nombreTarea' instalada: corre cada 2 horas y al iniciar sesion."
