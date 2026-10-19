param(
    [ValidateSet('Capture','Profile','Smoke','Benchmark')][string]$Phase='Capture',
    [ValidateSet('bistro','minecraft')][string]$Scene='bistro',
    [Parameter(Mandatory=$true)][string]$Label,
    [string]$OutputRoot='C:/Users/USER/Desktop/research/tmp/case19-20261019'
)
$ErrorActionPreference='Stop'
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process'}
$state=(& nvidia-smi --query-gpu=pstate,utilization.gpu --format=csv,noheader) -join ' '
if($LASTEXITCODE -ne 0 -or $state -notmatch '^P8,\s*(\d+)\s*%' -or [int]$Matches[1] -ge 20){throw "GPU not idle: $state"}
$games=@(Get-Process | Where-Object {$_.ProcessName -match '^(cs2|TslGame|VALORANT.*|League of Legends|Overwatch|dota2|FortniteClient.*|eldenring|GTA5.*|RDR2|Cyberpunk2077|blender|obs64)$'})
if($games.Count){throw 'Competing game or GPU work detected'}
& (Join-Path $PSScriptRoot 'run_color_blend_preservation.ps1') -Harness Case19 -Phase $Phase -Scene $Scene -Label $Label -OutputRoot $OutputRoot
