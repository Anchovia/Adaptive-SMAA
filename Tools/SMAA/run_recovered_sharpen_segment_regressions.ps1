$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$settings=Join-Path $repo 'Projects/CMAA2/ApplicationSettings.xml'
$original=[IO.File]::ReadAllBytes($settings);$source=[IO.File]::ReadAllText($settings)
$out=Join-Path $repo 'tmp/recovered-sharpen-segment/regressions.json';$records=@()
try {
 foreach($name in @('smaaTemporalLifecycleTest','smaaTemporalFeedbackTest','smaaEightCaseCapture')) {
  if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count-ne 0){throw 'CMAA2 already running'}
  [IO.File]::WriteAllText($settings,($source -replace '<SceneChoice>\d+</SceneChoice>','<SceneChoice>0</SceneChoice>'),[Text.UTF8Encoding]::new($false))
  $arguments=@("-$name")
  if($name-eq 'smaaEightCaseCapture'){$arguments+=@('"1 12 60"')}
  $text=@(& (Join-Path $repo 'Tools/SMAA/run_clean_cmaa2.ps1') -CMAA2Arguments $arguments -TimeoutSeconds 600 -Hidden)
  $text | ForEach-Object {Write-Output $_}
  if(($text -join "`n")-notmatch 'report=(.+_results.csv)'){throw 'Missing regression report'}
  $records+=[ordered]@{test=$name;status='PASS';report=$Matches[1];exe_sha256=(Get-FileHash (Join-Path $repo 'Projects/CMAA2/CMAA2.exe')).Hash;arguments=$arguments}
  ConvertTo-Json -InputObject @($records) -Depth 6 | Set-Content -LiteralPath $out -Encoding utf8
 }
} finally {[IO.File]::WriteAllBytes($settings,$original)}
