<#
    Crea el acceso directo "Canvas Downloader" en el Menú Inicio de Windows.
    Se corre una sola vez (y de nuevo si movés la carpeta o reinstalás Python).

    Uso (clic derecho > Ejecutar con PowerShell) o bien:
      powershell -ExecutionPolicy Bypass -File .\instalar_acceso_directo.ps1
#>
$ErrorActionPreference = 'Stop'

$proyecto = $PSScriptRoot
if (-not $proyecto) { $proyecto = Split-Path -Parent $MyInvocation.MyCommand.Path }

$lanzador = Join-Path $proyecto 'iniciar_canvas.pyw'
$icono    = Join-Path $proyecto 'canvas.ico'

if (-not (Test-Path $lanzador)) {
    throw "No encuentro iniciar_canvas.pyw en $proyecto"
}

# Buscamos un intérprete sin consola: pyw.exe (lanzador de Windows) o pythonw.exe.
$pyw = $null
$candidato = Get-Command 'pyw.exe' -ErrorAction SilentlyContinue
if ($candidato) { $pyw = $candidato.Source }
if (-not $pyw) {
    $python = Get-Command 'python.exe' -ErrorAction SilentlyContinue
    if ($python) {
        $posible = $python.Source -replace 'python\.exe$', 'pythonw.exe'
        if (Test-Path $posible) { $pyw = $posible }
    }
}
if (-not $pyw) {
    throw 'No encuentro pyw.exe ni pythonw.exe. Instala Python desde python.org y volve a correr esto.'
}

$carpetaInicio = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$destino = Join-Path $carpetaInicio 'Canvas Downloader.lnk'

$shell = New-Object -ComObject WScript.Shell
$acceso = $shell.CreateShortcut($destino)
$acceso.TargetPath       = $pyw
$acceso.Arguments        = '"' + $lanzador + '"'
$acceso.WorkingDirectory = $proyecto
$acceso.Description      = 'Descargador de material de Canvas LMS'
if (Test-Path $icono) { $acceso.IconLocation = $icono }
$acceso.Save()

Write-Output "Acceso directo creado: $destino"
Write-Output "  destino : $pyw"
Write-Output "  script  : $lanzador"
Write-Output ''
Write-Output 'Busca "Canvas Downloader" en el Menu Inicio. Con clic derecho podes anclarlo a Inicio o a la barra de tareas.'
