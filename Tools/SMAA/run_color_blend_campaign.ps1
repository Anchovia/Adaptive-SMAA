param(
    [Parameter(Mandatory=$true)][ValidateSet('Optimization','CleanupABBA','Profile')][string]$Stage,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
# Explicitly invoked after user authorization; one clean process per item.
# Runs existing binaries without rebuilding or copying files into old worktrees.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runner=Join-Path $PSScriptRoot 'run_color_blend_preservation.ps1'
foreach($scene in 'bistro','minecraft'){
    $gate=Get-Content -LiteralPath (Join-Path $root "Docs/Edge-History-Color-Blend-Optimization/verify-opt-d-$scene.json") -Raw | ConvertFrom-Json
    if($gate.validation -ne 'PASS' -or $gate.expected_modes -ne 6 -or $gate.frames_per_mode -ne 240){throw "RGB gate missing for $scene"}
}
$visual=Get-Content -LiteralPath (Join-Path $root 'Docs/Edge-History-Color-Blend-Optimization/visual-inspection-opt-d.json') -Raw | ConvertFrom-Json
if($visual.output_preservation_review -ne 'PASS'){throw 'Direct original-frame review is incomplete'}

function Invoke-Item([string]$Harness,[string]$Phase,[string]$Scene,[string]$Label,[string]$Worktree){
    if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'CMAA2 process already running'}
    # A fixed inter-process gap is only a startup-stall mitigation hypothesis.
    Start-Sleep -Seconds 10
    $idle=$false
    for($attempt=0;$attempt -lt 20;$attempt++){
        $state=(& nvidia-smi --query-gpu=pstate,utilization.gpu --format=csv,noheader) -join ' '
        if($LASTEXITCODE -ne 0){throw 'Cannot inspect GPU'}
        if($state -match '^P8,\s*(\d+)\s*%' -and [int]$Matches[1] -lt 20){$idle=$true;break}
        Start-Sleep -Seconds 3
    }
    if(!$idle){throw "GPU did not become idle before $Scene/$Phase/${Label}: $state"}
    $games=@(Get-Process | Where-Object {$_.ProcessName -match '^(cs2|TslGame|VALORANT.*|League of Legends|Overwatch|dota2|FortniteClient.*|eldenring|GTA5.*|RDR2|Cyberpunk2077|blender|obs64)$'})
    if($games.Count){throw 'Competing game or GPU work detected; no measurement started'}
    Write-Output "START $Stage $Scene $Phase $Label ($Worktree); GPU $state"
    & $runner -Harness $Harness -Phase $Phase -Scene $Scene -Label $Label -OutputRoot $OutputRoot -WorktreeRoot $Worktree
    if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Residual CMAA2 process after run'}
    Write-Output "DONE $Scene $Phase $Label"
}

if($Stage -eq 'Optimization'){
    foreach($scene in 'bistro','minecraft'){Invoke-Item 'Optimization' 'Smoke' $scene 'opt-smoke-b' $root}
    foreach($scene in 'bistro','minecraft'){Invoke-Item 'Optimization' 'Benchmark' $scene 'opt-bench-b' $root}
}elseif($Stage -eq 'Profile'){
    foreach($scene in 'bistro','minecraft'){Invoke-Item 'Optimization' 'Profile' $scene 'opt-profile-b' $root}
}else{
    $before=(Resolve-Path (Join-Path $root '../c17-before')).Path
    $after=(Resolve-Path (Join-Path $root '../c17-cleanup')).Path
    $expected=@{$before='CA01DDD6602ABC129A49D246B7D93C17E4F92FC3E0570E9DE92864792130B739';$after='47E69FD5B3073FDFFBD364FA5F2F3B55ED5107C893B1345E701D2EBBF586D212'}
    foreach($path in $before,$after){
        if((Get-FileHash -LiteralPath (Join-Path $path 'Projects/CMAA2/CMAA2.exe')).Hash -ne $expected[$path]){throw "Unexpected ABBA binary: $path"}
    }
    foreach($path in $before,$after){foreach($scene in 'bistro','minecraft'){
        $label=if($path -eq $before){'before-smoke-1'}else{'after-smoke-1'}
        Invoke-Item 'Preservation' 'Smoke' $scene $label $path
    }}
    foreach($item in @(@($before,'before-bench-1'),@($after,'after-bench-1'),@($after,'after-bench-2'),@($before,'before-bench-2'))){
        foreach($scene in 'bistro','minecraft'){Invoke-Item 'Preservation' 'Benchmark' $scene $item[1] $item[0]}
    }
}
Write-Output "PASS: $Stage campaign completed"
