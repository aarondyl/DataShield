param([Parameter(Mandatory=$true)][string]$Executable)
$ErrorActionPreference = 'Stop'
$dataDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('datashield-smoke-' + [guid]::NewGuid())
New-Item -ItemType Directory $dataDirectory | Out-Null
$env:LOCAL_DATA_DIR = $dataDirectory
$env:RUNTIME_MODE = 'local'
$env:RUN_SEED = 'false'
$env:DATASHIELD_SIDECAR_DIAGNOSTICS = '1'
$previousToken = $env:RUNTIME_TOKEN
$env:RUNTIME_TOKEN = 'smoke-inherited-token-must-not-be-used'
$process = Start-Process -FilePath (Resolve-Path $Executable) -PassThru
try {
  $descriptorPath = Join-Path $dataDirectory 'runtime.json'
  $ready = $false
  for ($attempt = 0; $attempt -lt 90; $attempt++) {
    if ($process.HasExited) { throw 'Packaged sidecar exited before readiness' }
    if (Test-Path $descriptorPath) {
      $descriptor = Get-Content $descriptorPath -Raw | ConvertFrom-Json
      if ($descriptor.pid -ne $process.Id) { throw 'Runtime PID mismatch' }
      if ($descriptor.runtime_token -eq $env:RUNTIME_TOKEN) { throw 'Runtime reused an inherited token' }
      if ($descriptor.base_url -notmatch '^http://127\.0\.0\.1:[0-9]+$') { throw 'Runtime must use dynamic loopback' }
      try {
        $health = Invoke-RestMethod ($descriptor.base_url + '/api/health') -TimeoutSec 2
        $ready = $true
        break
      } catch { }
    }
    Start-Sleep -Seconds 1
  }
  if (-not $ready) { throw 'Packaged sidecar did not become ready' }
  # Never print the descriptor or token; check authorization with a harmless read.
  $denied = $false
  try { Invoke-RestMethod ($descriptor.base_url + '/api/companies') -TimeoutSec 5 | Out-Null }
  catch { $denied = [int]$_.Exception.Response.StatusCode -eq 401 }
  if (-not $denied) { throw 'Private API accepted a request without runtime token' }
  Invoke-RestMethod ($descriptor.base_url + '/api/companies') -Headers @{'X-Runtime-Token'=$descriptor.runtime_token} -TimeoutSec 5 | Out-Null
  Write-Host 'Packaged sidecar readiness, PID, loopback and runtime authorization passed'
} catch {
  $logFile = Join-Path $dataDirectory 'sidecar-startup.log'
  if (Test-Path $logFile) { Get-Content $logFile -Tail 60 | Write-Host }
  throw
} finally {
  if (-not $process.HasExited) { Stop-Process -Id $process.Id; $process.WaitForExit() }
  Remove-Item Env:LOCAL_DATA_DIR
  Remove-Item Env:DATASHIELD_SIDECAR_DIAGNOSTICS
  if ($null -eq $previousToken) { Remove-Item Env:RUNTIME_TOKEN } else { $env:RUNTIME_TOKEN = $previousToken }
}
