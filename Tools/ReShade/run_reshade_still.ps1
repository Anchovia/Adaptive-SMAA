param(
    [ValidateSet('bistro','minecraft')][string]$Scene='bistro',
    [Parameter(Mandatory=$true)][string]$Label,
    [string]$Bundle='D:\SMAAResearchCaptures\reshade\bundle-staging',
    [string]$OutputRoot='D:\SMAAResearchCaptures\rs1',
    [int]$MinIdleSeconds=60,
    [int]$WaitForIdleMinutes=30,
    [int]$TimeoutSeconds=900
)
# Runs the CMAA2 demo with the ReShade bundle injected (dxgi.dll) from a temporary copy of the executable
# folder, so the build folder never holds dxgi.dll. The demo's own AA is off and its UI hidden
# (-smaaReShadeStillCapture). At each of three fixed poses the script switches ReShade presets with posted
# key messages and saves ReShade's Before/After PNG screenshots:
#   F7 Original SMAA Ultra (SMAA.fx), F8 Adaptive SMAA Ultra, F5 Adaptive tier view (DebugOutput 3),
#   F6 Adaptive with every tier at the preset maximum (ADAPTIVE_SMAA_TIERS_AT_PRESET_MAX=1, recompiles).
# The copy is deleted at the end, also after a failure.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$source=Join-Path $root 'Projects\CMAA2'
$test=Join-Path $root 'Projects\CMAA2_RS'
$output=Join-Path $OutputRoot $Label
$handshake=Join-Path $output 'hs'
if(Test-Path -LiteralPath $test){throw "Test copy already exists: $test"}
if(Test-Path -LiteralPath $output){throw "Output already exists: $output"}
if(Test-Path -LiteralPath (Join-Path $source 'dxgi.dll')){throw 'dxgi.dll found in the build folder'}

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class RsWin {
    [StructLayout(LayoutKind.Sequential)] struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO info);
    [DllImport("kernel32.dll")] static extern uint GetTickCount();
    public static double IdleSeconds() {
        var info = new LASTINPUTINFO(); info.cbSize = (uint)Marshal.SizeOf(info);
        GetLastInputInfo(ref info); return (GetTickCount() - info.dwTime) / 1000.0;
    }
    delegate bool EnumProc(IntPtr hwnd, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc proc, IntPtr lParam);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int l, t, r, b; }
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr hwnd, out RECT rect);
    public static IntPtr FindLargestWindow(uint pid) {
        IntPtr best = IntPtr.Zero; long bestArea = 0;
        EnumWindows((h, p) => {
            uint owner; GetWindowThreadProcessId(h, out owner);
            if (owner == pid) { RECT r; GetClientRect(h, out r); long a = (long)(r.r - r.l) * (r.b - r.t); if (a > bestArea) { bestArea = a; best = h; } }
            return true;
        }, IntPtr.Zero);
        return best;
    }
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint mapType);
    public static bool KeyDown(IntPtr hwnd, uint vk) { uint scan = MapVirtualKey(vk, 0); return PostMessage(hwnd, 0x0100, (IntPtr)vk, (IntPtr)(1 | (scan << 16))); }
    public static bool KeyUp(IntPtr hwnd, uint vk) { uint scan = MapVirtualKey(vk, 0); return PostMessage(hwnd, 0x0101, (IntPtr)vk, (IntPtr)unchecked((int)(1u | (scan << 16) | (1u << 30) | (1u << 31)))); }
}
'@

function Get-EnvFolders {
    $map=[ordered]@{}
    foreach($p in @("$env:TEMP\ReShade","$env:LOCALAPPDATA\ReShade","$env:APPDATA\ReShade","$env:ProgramData\ReShade")){
        $map[$p]=if(Test-Path -LiteralPath $p){@(Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue).Count}else{-1}
    }
    return $map
}

# Preconditions: no CMAA2 process, idle GPU, nobody using the PC.
if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process; no new run started'}
$gpuBefore=@(& nvidia-smi --query-gpu=name,driver_version,pstate,utilization.gpu,memory.used --format=csv,noheader)
if($LASTEXITCODE -ne 0){throw 'Cannot verify GPU state'}
if($gpuBefore[0] -notmatch ', P8,'){throw "GPU is not idle (P8): $($gpuBefore[0])"}
$gpuProcesses=@(& nvidia-smi)
$idleDeadline=(Get-Date).AddMinutes($WaitForIdleMinutes)
while(($idle=[RsWin]::IdleSeconds()) -lt $MinIdleSeconds){
    if((Get-Date) -gt $idleDeadline){throw "User input $([math]::Round($idle,1)) s ago; not starting"}
    Start-Sleep -Seconds 10
}
$gpuBefore=@(& nvidia-smi --query-gpu=name,driver_version,pstate,utilization.gpu,memory.used --format=csv,noheader)
if($gpuBefore[0] -notmatch ', P8,'){throw "GPU is not idle (P8) after waiting for input idle: $($gpuBefore[0])"}
$gpuProcesses=@(& nvidia-smi)
$envBefore=Get-EnvFolders

New-Item -ItemType Directory -Path $handshake -Force | Out-Null
$shots=Join-Path $output 'shots'
New-Item -ItemType Directory -Path $shots -Force | Out-Null
$events=New-Object System.Collections.Generic.List[object]
function Add-Event($what){$events.Add([pscustomobject]@{utc=[DateTime]::UtcNow.ToString('o');event=$what})|Out-Null;Write-Output $what}

$process=$null
$result='FAIL'
$failure=''
try {
    # Temporary copy at the same depth so ../../Modules shader paths resolve.
    New-Item -ItemType Directory -Path $test | Out-Null
    foreach($f in 'CMAA2.exe','ApplicationSettings.xml'){Copy-Item -LiteralPath (Join-Path $source $f) -Destination $test}
    foreach($d in 'CMAA2','SMAA','FXAA','Media','cache'){Copy-Item -LiteralPath (Join-Path $source $d) -Destination $test -Recurse}
    $exe=Join-Path $test 'CMAA2.exe'
    $exeHash=(Get-FileHash -LiteralPath $exe).Hash
    if($exeHash -ne (Get-FileHash -LiteralPath (Join-Path $source 'CMAA2.exe')).Hash){throw 'Executable copy differs'}
    $settings=Join-Path $test 'ApplicationSettings.xml'
    $content=[System.IO.File]::ReadAllText($settings)
    $sceneIndex=if($Scene -eq 'bistro'){0}else{2}
    foreach($entry in ([ordered]@{WindowPositionX=-1;WindowPositionY=-1;WindowClientSizeX=1920;WindowClientSizeY=1061;FullscreenState=1;SceneChoice=$sceneIndex;CurrentAAOption=0}).GetEnumerator()){
        $pattern="<$($entry.Key)>-?\d+</$($entry.Key)>"
        if(([regex]::Matches($content,$pattern)).Count -ne 1){throw "Unexpected setting: $($entry.Key)"}
        $content=[regex]::Replace($content,$pattern,"<$($entry.Key)>$($entry.Value)</$($entry.Key)>")
    }
    [System.IO.File]::WriteAllText($settings,$content)

    # ReShade files from the bundle, with test-only settings.
    Copy-Item -Path (Join-Path $Bundle 'game-folder\*') -Destination $test -Recurse
    $presetDir=Join-Path $test 'ReShade-AdaptiveSMAA-Presets'
    $adaptive=[System.IO.File]::ReadAllText((Join-Path $presetDir 'Adaptive-SMAA-Ultra.ini'))
    if($adaptive -notmatch 'DebugOutput=0'){throw 'Unexpected Adaptive preset'}
    [System.IO.File]::WriteAllText((Join-Path $presetDir 'Adaptive-SMAA-Ultra-TierView.ini'),($adaptive -replace 'DebugOutput=0','DebugOutput=3'))
    [System.IO.File]::WriteAllText((Join-Path $presetDir 'Adaptive-SMAA-Ultra-TiersAtMax.ini'),($adaptive -replace '\[AdaptiveSMAA.fx\]',"[AdaptiveSMAA.fx]`r`nPreprocessorDefinitions=ADAPTIVE_SMAA_TIERS_AT_PRESET_MAX=1"))
    $ini=Join-Path $test 'ReShade.ini'
    $text=[System.IO.File]::ReadAllText($ini)
    $replacements=[ordered]@{
        'PresetShortcutKeys=118,0,0,0,119,0,0,0'='PresetShortcutKeys=118,0,0,0,119,0,0,0,116,0,0,0,117,0,0,0';
        "Adaptive-SMAA-Ultra.ini`r`n"="Adaptive-SMAA-Ultra.ini,.\ReShade-AdaptiveSMAA-Presets\Adaptive-SMAA-Ultra-TierView.ini,.\ReShade-AdaptiveSMAA-Presets\Adaptive-SMAA-Ultra-TiersAtMax.ini`r`nIntermediateCachePath=.\reshade-cache`r`n";
        'KeyScreenshot=44,0,0,0'='KeyScreenshot=120,0,0,0';
        'SavePath=.\ReShade-Screenshots'='SavePath=.\rs-shots';
        'FileNaming=%AppName% %Date% %Time%_%Count% %PresetName% %BeforeAfter%'='FileNaming=shot_%Count% %PresetName% %BeforeAfter%';
        'SavePresetFile=0'='SavePresetFile=1'
    }
    foreach($r in $replacements.GetEnumerator()){
        $count=([regex]::Matches($text,[regex]::Escape($r.Key))).Count
        if($count -ne 1){throw "ReShade.ini: '$($r.Key)' found $count times"}
        $text=$text.Replace($r.Key,$r.Value)
    }
    [System.IO.File]::WriteAllText($ini,$text)
    New-Item -ItemType Directory -Path (Join-Path $test 'reshade-cache') | Out-Null
    $shotDir=Join-Path $test 'rs-shots'
    New-Item -ItemType Directory -Path $shotDir | Out-Null
    $log=Join-Path $test 'ReShade.log'

    $process=Start-Process -FilePath $exe -ArgumentList @('-smaaReShadeStillCapture',$Scene,$handshake,'-smaaNonInteractiveShaderCompile') -WorkingDirectory $test -WindowStyle Hidden -PassThru
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    Add-Event "started PID $($process.Id)"

    function Wait-For([scriptblock]$condition,[string]$what){
        while(-not (& $condition)){
            if($process.HasExited){throw "CMAA2 exited while waiting for $what"}
            if((Get-Date) -gt $deadline){throw "Timeout while waiting for $what"}
            Start-Sleep -Milliseconds 200
        }
    }
    function Get-LogText {
        # ReShade keeps the log open for writing, so read it with full sharing.
        if(-not (Test-Path -LiteralPath $log)){return ''}
        $stream=[System.IO.File]::Open($log,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]'ReadWrite,Delete')
        try{$reader=New-Object System.IO.StreamReader($stream);return $reader.ReadToEnd()}finally{$stream.Dispose()}
    }
    function Send-Key([uint32]$vk,[string]$name){
        $hwnd=[RsWin]::FindLargestWindow([uint32]$process.Id)
        if($hwnd -eq [IntPtr]::Zero){throw 'No window for the CMAA2 process'}
        if(-not [RsWin]::KeyDown($hwnd,$vk)){throw "PostMessage failed for $name"}
        Start-Sleep -Milliseconds 150
        [void][RsWin]::KeyUp($hwnd,$vk)
        Add-Event "key $name"
    }

    $steps=@(
        @{name='original';vk=118;preset='Original-SMAA-Ultra'},
        @{name='adaptive';vk=119;preset='Adaptive-SMAA-Ultra'},
        @{name='tierview';vk=116;preset='Adaptive-SMAA-Ultra-TierView'},
        @{name='tiersatmax';vk=117;preset='Adaptive-SMAA-Ultra-TiersAtMax'}
    )
    $compiledAdaptive="Successfully compiled '[^']*\\AdaptiveSMAA\.fx'"
    $compiledOriginal="Successfully compiled '[^']*\\SweetFX\\SMAA\.fx'"
    $current='Original-SMAA-Ultra'
    $records=@()
    for($pose=0;$pose -lt 3;$pose++){
        Wait-For {Test-Path -LiteralPath (Join-Path $handshake "ready_$pose.txt")} "ready_$pose"
        Add-Event "ready $pose"
        if($pose -eq 0){
            Wait-For {$l=Get-LogText; ($l -match $compiledAdaptive -and $l -match $compiledOriginal) -or $l -match 'Failed to compile'} 'effect compilation'
            if((Get-LogText) -match 'Failed to compile'){throw 'ReShade failed to compile an effect'}
            Start-Sleep -Seconds 3
        }
        foreach($step in $steps){
            $reload=($step.preset -like '*TiersAtMax') -ne ($current -like '*TiersAtMax')
            $logBefore=(Get-LogText).Length
            if($step.preset -ne $current){Send-Key $step.vk $step.name}
            if($reload){
                # All effects reload when the preprocessor definitions change.
                Wait-For {$l=(Get-LogText).Substring($logBefore); ($l -match $compiledAdaptive -and $l -match $compiledOriginal) -or $l -match 'Failed to compile'} "effect reload for $($step.name)"
                if((Get-LogText).Substring($logBefore) -match 'Failed to compile'){throw "ReShade failed to compile during the reload for $($step.name)"}
            }
            Start-Sleep -Seconds 2
            $current=$step.preset
            $before=@(Get-ChildItem -LiteralPath $shotDir -File | ForEach-Object {$_.Name})
            Send-Key 120 'F9 screenshot'
            $newFiles=$null
            Wait-For {
                $now=@(Get-ChildItem -LiteralPath $shotDir -File | Where-Object {$before -notcontains $_.Name})
                $png=@($now | Where-Object {$_.Extension -eq '.png'})
                if($png.Count -ge 2 -and @($now | Where-Object {$_.Extension -eq '.ini'}).Count -ge 1){
                    $sizes1=($now | ForEach-Object {$_.Length}) -join ','
                    Start-Sleep -Milliseconds 800
                    $again=@(Get-ChildItem -LiteralPath $shotDir -File | Where-Object {$before -notcontains $_.Name})
                    if((($again | ForEach-Object {$_.Length}) -join ',') -eq $sizes1){$script:newFiles=$again;return $true}
                }
                return $false
            } "screenshot $pose $($step.name)"
            $files=$script:newFiles
            if(@($files).Count -ne 3){throw "Expected 3 new files for $pose $($step.name), got $(@($files).Count)"}
            $beforePng=@($files | Where-Object {$_.Name -match ' Before\.png$'})
            $afterPng=@($files | Where-Object {$_.Name -match ' After\.png$'})
            $presetCopy=@($files | Where-Object {$_.Extension -eq '.ini'})
            if($beforePng.Count -ne 1 -or $afterPng.Count -ne 1 -or $presetCopy.Count -ne 1){throw "Unexpected screenshot names: $(($files|ForEach-Object Name) -join '; ')"}
            if($afterPng[0].Name -notmatch [regex]::Escape($step.preset)+' After\.png$'){throw "Active preset mismatch: $($afterPng[0].Name)"}
            $base="p$($pose)_$($step.name)"
            Move-Item -LiteralPath $beforePng[0].FullName -Destination (Join-Path $shots "$base`_before.png")
            Move-Item -LiteralPath $afterPng[0].FullName -Destination (Join-Path $shots "$base`_after.png")
            Move-Item -LiteralPath $presetCopy[0].FullName -Destination (Join-Path $shots "$base`_preset.ini")
            $records+=[pscustomobject]@{pose=$pose;step=$step.name;preset=$step.preset;reloaded=$reload;source_after=$afterPng[0].Name;
                before_sha256=(Get-FileHash -LiteralPath (Join-Path $shots "$base`_before.png")).Hash;after_sha256=(Get-FileHash -LiteralPath (Join-Path $shots "$base`_after.png")).Hash}
            Add-Event "saved $base"
        }
        [System.IO.File]::WriteAllText((Join-Path $handshake "shot_$pose.txt"),"$pose")
    }
    if(-not $process.WaitForExit([int][math]::Max(1000,($deadline-(Get-Date)).TotalMilliseconds))){throw 'CMAA2 did not exit after the last pose'}
    if($process.ExitCode -ne 0){throw "CMAA2 exited with code $($process.ExitCode)"}
    Add-Event "exited 0"
    $reports=@(Get-ChildItem -LiteralPath (Join-Path $test 'AutoBench') -Recurse -File -Filter '*_results.csv' -ErrorAction SilentlyContinue)
    if($reports.Count -ne 1){throw "Expected one AutoBench report, found $($reports.Count)"}
    $reportText=[System.IO.File]::ReadAllText($reports[0].FullName)
    Copy-Item -LiteralPath $reports[0].FullName -Destination (Join-Path $output 'report.csv')
    if($reportText -notmatch 'Aggregate: PASS' -or $reportText -match '(?im),\s*FAIL\s*(?:,|$)'){throw 'Harness report is not PASS'}
    $result='PASS'
} catch {
    $failure=$_.Exception.Message
    Add-Event "failure: $failure"
} finally {
    if($process -and -not $process.HasExited){
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        $process.WaitForExit()
        Add-Event "terminated PID $($process.Id)"
    }
    Start-Sleep -Milliseconds 500
    $remaining=@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count
    foreach($f in 'ReShade.log','ReShade.ini'){if(Test-Path -LiteralPath (Join-Path $test $f)){Copy-Item -LiteralPath (Join-Path $test $f) -Destination (Join-Path $output "reshade-after-run_$f")}}
    if(Test-Path -LiteralPath (Join-Path $test 'ReShade-AdaptiveSMAA-Presets')){Copy-Item -LiteralPath (Join-Path $test 'ReShade-AdaptiveSMAA-Presets') -Destination (Join-Path $output 'presets-after-run') -Recurse}
    $logLines=if(Test-Path -LiteralPath (Join-Path $output 'reshade-after-run_ReShade.log')){@(Get-Content -LiteralPath (Join-Path $output 'reshade-after-run_ReShade.log'))}else{@()}
    $errorLines=@($logLines | Where-Object {$_ -match '\|\s*ERROR\s*\|'})
    $warningLines=@($logLines | Where-Object {$_ -match '\|\s*WARN(ING)?\s*\|'})
    $compiled=@($logLines | Where-Object {$_ -match 'Successfully compiled'})
    if(Test-Path -LiteralPath $test){Remove-Item -LiteralPath $test -Recurse -Force}
    $envAfter=Get-EnvFolders
    $record=[pscustomobject]@{label=$Label;scene=$Scene;result=$result;failure=$failure;remaining_cmaa2=$remaining;test_copy_removed=-not (Test-Path -LiteralPath $test);
        build_folder_dxgi=(Test-Path -LiteralPath (Join-Path $source 'dxgi.dll'));idle_seconds_at_start=$idle;gpu_before=$gpuBefore;gpu_processes_before=$gpuProcesses;
        executable_sha256=$exeHash;bundle=$Bundle;bundle_manifest_sha256=(Get-FileHash -LiteralPath (Join-Path $Bundle 'MANIFEST-sha256.txt')).Hash;
        reshade_errors=$errorLines;reshade_warnings=$warningLines;reshade_compiled=$compiled;env_folders_before=$envBefore;env_folders_after=$envAfter;shots=$records;events=$events}
    ConvertTo-Json -InputObject $record -Depth 6 | Set-Content -LiteralPath (Join-Path $output 'run.json') -Encoding utf8
    if($remaining -ne 0){throw 'CMAA2 process still running after the run'}
}
if($result -ne 'PASS'){throw "Run failed: $failure"}
Write-Output "PASS: $output"
