param(
    [string]$CondaEnv = 'helth',
    [string]$ListenHost = '127.0.0.1',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

function Resolve-EnvPython {
    param([string]$CondaEnv)

    $candidates = @(
        (Join-Path $env:USERPROFILE ".conda\envs\$CondaEnv\python.exe"),
        (Join-Path $env:USERPROFILE "miniconda3\envs\$CondaEnv\python.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\envs\$CondaEnv\python.exe"),
        (Join-Path $env:LOCALAPPDATA "anaconda3\envs\$CondaEnv\python.exe")
    ) | Where-Object { $_ }

    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return $path
        }
    }

    throw "Cannot find python.exe for conda env '$CondaEnv'."
}

$python = Resolve-EnvPython -CondaEnv $CondaEnv
$proc = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'backend.main:app', '--host', $ListenHost, '--port', "$Port") -WorkingDirectory $root -PassThru
try {
    $baseUrl = "http://$ListenHost`:$Port"
    $ready = $false
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Seconds 1
        try {
            $resp = Invoke-RestMethod -Uri "$baseUrl/healthz" -TimeoutSec 2
            if ($resp.status -eq 'ok') {
                $ready = $true
                break
            }
        }
        catch {
        }
    }

    if (-not $ready) {
        throw 'Backend did not become ready in time.'
    }

    $healthz = Invoke-RestMethod -Uri "$baseUrl/healthz"
    $system = Invoke-RestMethod -Uri "$baseUrl/api/v1/system/info"
    $devices = Invoke-RestMethod -Uri "$baseUrl/api/v1/devices"

    [pscustomobject]@{
        healthz = $healthz
        system_info = $system
        device_count = @($devices).Count
    } | ConvertTo-Json -Depth 6
}
finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
    }
}
