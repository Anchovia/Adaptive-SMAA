param([switch] $Capture)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Push-Location $root
try {
 $dir=Join-Path $root ('tmp/shader-lifetime-gate-'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
 New-Item -ItemType Directory -Path $dir | Out-Null
 $hash=(Get-FileHash Projects/CMAA2/CMAA2.exe).Hash
 $records=@()
 foreach($kind in @('buffer','file')) {
  $rejected=$false
  try { & Tools/SMAA/run_clean_cmaa2.ps1 -CMAA2Arguments @('-smaaShaderFailureTest',$kind) -Hidden -TimeoutSeconds 30 }
  catch { if($_.Exception.Message -notmatch 'exited with code 1$') {throw}; $rejected=$true }
  if(!$rejected) {throw 'Expected compile failure was not rejected'}
  $log=Get-Content Projects/CMAA2/log.txt -Raw
  if($log -notmatch 'EXPECTED_SHADER_FAILURE_TEST' -or $log -notmatch 'NONINTERACTIVE_SHADER_COMPILE_FAILURE' -or $log -notmatch 'intentionally_missing_symbol') {throw 'Missing expected compile diagnostic'}
  Copy-Item -LiteralPath Projects/CMAA2/log.txt -Destination (Join-Path $dir "failure-$kind.log")
  $records += [pscustomobject]@{kind="expected-$kind-failure";exit_code=1;executable_sha256=$hash}
  $records | ConvertTo-Json | Set-Content (Join-Path $dir 'checks.json')
  Write-Output "PASS: expected $kind compile failure rejected"
 }
 for($i=0;$i -lt 3;$i++) {
  $out=& Tools/SMAA/run_clean_cmaa2.ps1 -CMAA2Arguments @('-smaaShaderLifetimeTest') -Hidden -TimeoutSeconds 120
  $line=$out | Where-Object {$_ -match 'PASS:.*report='} | Select-Object -Last 1
  if(!$line) {throw 'Missing lifetime report'}
  $records += [pscustomobject]@{kind='lifetime';exit_code=0;executable_sha256=$hash;report=($line -split 'report=',2)[1].Trim()}
  $records | ConvertTo-Json | Set-Content (Join-Path $dir 'checks.json')
  Write-Output $line
 }
 for($i=0;$i -lt 3;$i++) {
  foreach($scene in @('bistro','minecraft')) {
   & Tools/SMAA/run_temporal_dependency.ps1 -Phase Smoke -Scene $scene -Receipt (Join-Path $dir 'smokes.json')
  }
 }
 if($Capture) {
  foreach($scene in @('bistro','minecraft')) {
   & Tools/SMAA/run_temporal_dependency.ps1 -Phase Capture -Scene $scene -Receipt (Join-Path $dir 'captures.json')
  }
 }
 if((Get-FileHash Projects/CMAA2/CMAA2.exe).Hash -ne $hash) {throw 'Executable changed during gate'}
 if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count) {throw 'Residual CMAA2 process'}
 Write-Output "PASS: completed lifetime gate; receipts=$dir"
} finally {Pop-Location}
