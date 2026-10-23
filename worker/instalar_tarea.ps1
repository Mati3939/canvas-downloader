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
$pythonw = (Get-Command pythonw).Source

$accion = New-ScheduledTaskAction -Execute $pythonw -Argument "-m worker.run" `
    -WorkingDirectory $repo

$disparadorInicio = New-ScheduledTaskTrigger -AtLogOn

$disparadorPeriodico = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 2) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

$config = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

$tareaExistente = Get-ScheduledTask -TaskName $nombreTarea -ErrorAction SilentlyContinue
if ($tareaExistente) {
    Unregister-ScheduledTask -TaskName $nombreTarea -Confirm:$false
}

Register-ScheduledTask -TaskName $nombreTarea `
    -Action $accion `
    -Trigger @($disparadorInicio, $disparadorPeriodico) `
    -Settings $config `
    -Principal $principal | Out-Null

Write-Host "Tarea '$nombreTarea' instalada: corre cada 2 horas y al iniciar sesion."
