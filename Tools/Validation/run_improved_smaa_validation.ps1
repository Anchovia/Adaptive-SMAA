param(
    [ValidateSet('Capture','Showcase','Screens','Keys','Translation','DtRecord')][string]$Mode='Capture',
    [ValidateSet('h','v')][string]$Direction='h',
    [string]$DtCsv='',
    [ValidateSet('bistro','minecraft')][string]$Scene='bistro',
    [Parameter(Mandatory=$true)][string]$Label,
    [string]$OutputRoot='D:\SMAAResearchCaptures\c32',
    [int]$TimeoutSeconds=2400,
    [int]$MinIdleSeconds=60,
    [int]$WaitForIdleMinutes=30
)
# One clean CMAA2 process per command for the improved SMAA demo validation harness
# (Projects/CMAA2/ImprovedSmaaValidation.inl). Capture runs in a hidden window, the other modes in a visible one.
# Preconditions: no CMAA2 process, idle GPU (P8), no user input for MinIdleSeconds.
# Postconditions: exit code 0, no CMAA2 process left, and a new AutoBench report with Aggregate PASS and no
# FAIL row (Capture, Showcase), the three saved screens (Screens) or the key test below (Keys). Screens and Keys
# run without AutoBench.
# Translation (hidden window, AutoBench) runs -translationCapture <scene> <h|v> <DtCsv> <output>; DtRecord (visible
# window, no AutoBench) runs -translationDtRecord and must leave dt.csv with 1800 frame times.
# Keys presses the real keys T, Y, F1, Y, F1 in the CMAA2 window (keybd_event) and checks the state that keys.log
# records with each screen. It waits until the foreground lock timeout has passed since the last user input, so the
# demo window can come to the front, and sends a key only while the foreground window belongs to the started
# process; otherwise it stops without sending.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$exe=Join-Path $root 'Projects\CMAA2\CMAA2.exe'
$output=Join-Path $OutputRoot $Label
if(Test-Path -LiteralPath $output){throw "Output already exists: $output"}

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ImpIdle {
    [StructLayout(LayoutKind.Sequential)] struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO info);
    [DllImport("kernel32.dll")] static extern uint GetTickCount();
    public static double Seconds() { var i = new LASTINPUTINFO(); i.cbSize = (uint)Marshal.SizeOf(i); GetLastInputInfo(ref i); return (GetTickCount() - i.dwTime) / 1000.0; }
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool SystemParametersInfo(uint action, uint param, ref uint value, uint winIni);
    [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint mapType);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    public static uint ForegroundPid() { uint pid; GetWindowThreadProcessId(GetForegroundWindow(), out pid); return pid; }
    public static uint ForegroundLockTimeoutMs() { uint v = 0; SystemParametersInfo(0x2000, 0, ref v, 0); return v; }
    public static void Down(byte vk) { keybd_event(vk, (byte)MapVirtualKey(vk, 0), 0, UIntPtr.Zero); }
    public static void Up(byte vk) { keybd_event(vk, (byte)MapVirtualKey(vk, 0), 2, UIntPtr.Zero); }
}
'@

if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process; no new run started'}
$lockTimeoutMs=[ImpIdle]::ForegroundLockTimeoutMs()
$needIdle=if($Mode -eq 'Keys'){[math]::Max($MinIdleSeconds,[math]::Ceiling($lockTimeoutMs/1000)+10)}else{$MinIdleSeconds}
$deadline=(Get-Date).AddMinutes($WaitForIdleMinutes)
while(($idle=[ImpIdle]::Seconds()) -lt $needIdle){
    if((Get-Date) -gt $deadline){throw "User input $([math]::Round($idle,1)) s ago; not starting"}
    Start-Sleep -Seconds 10
}
# The GPU can stay above P8 for a while after the previous run; wait up to 90 s.
$p8Until=(Get-Date).AddSeconds(90)
do{$gpu=@(& nvidia-smi --query-gpu=name,driver_version,pstate,utilization.gpu,memory.used --format=csv,noheader); if($gpu[0] -match ', P8,'){break}; Start-Sleep -Seconds 5}while((Get-Date) -lt $p8Until)
if($LASTEXITCODE -ne 0 -or $gpu[0] -notmatch ', P8,'){throw "GPU is not idle (P8): $gpu"}
$gpuProcesses=@(& nvidia-smi)

# Window and start scene: windowed 1920x1061 client area, AA None until the harness (or the T key) selects one.
$settings=Join-Path $root 'Projects\CMAA2\ApplicationSettings.xml'
if(!(Test-Path -LiteralPath $settings)){throw "Missing $settings (start the demo once or copy one in)"}
$content=[System.IO.File]::ReadAllText($settings)
$sceneIndex=if($Scene -eq 'bistro'){0}else{2}
foreach($entry in ([ordered]@{WindowPositionX=-1;WindowPositionY=-1;WindowClientSizeX=1920;WindowClientSizeY=1061;FullscreenState=1;SceneChoice=$sceneIndex;CurrentAAOption=0}).GetEnumerator()){
    $pattern="<$($entry.Key)>-?\d+</$($entry.Key)>"
    if(([regex]::Matches($content,$pattern)).Count -ne 1){throw "Unexpected setting: $($entry.Key)"}
    $content=[regex]::Replace($content,$pattern,"<$($entry.Key)>$($entry.Value)</$($entry.Key)>")
}
[System.IO.File]::WriteAllText($settings,$content)

$exeHash=(Get-FileHash -LiteralPath $exe).Hash
$git=@('-c','gc.auto=0','-c',"safe.directory=$($root.Replace('\','/'))",'-C',$root)
$head=(& git @git rev-parse HEAD).Trim()
$dirty=@(& git @git status --porcelain --untracked-files=no -- Projects).Count -ne 0
$autoBench=Join-Path $root 'Projects\CMAA2\AutoBench'
$before=@(Get-ChildItem -LiteralPath $autoBench -Recurse -File -Filter '*_results.csv' -ErrorAction SilentlyContinue | ForEach-Object {$_.FullName})
New-Item -ItemType Directory -Path $output | Out-Null
$started=[DateTime]::UtcNow.ToString('o')
$style=if($Mode -eq 'Capture' -or $Mode -eq 'Translation'){'Hidden'}else{'Normal'}
$arguments=switch($Mode){'Translation'{@('-translationCapture',$Scene,$Direction,$DtCsv,$output)}'DtRecord'{@('-translationDtRecord',$Scene,$output)}default{@("-improvedSmaa$Mode",$Scene,$output)}}
if($Mode -eq 'Translation' -and !(Test-Path -LiteralPath $DtCsv)){throw "Missing dt csv: $DtCsv"}
$process=Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory (Split-Path $exe) -WindowStyle $style -PassThru

$keyFailure='';$keySteps=@()
if($Mode -eq 'Keys'){
    $log=Join-Path $output 'keys.log'
    $waitFor={param([scriptblock]$test,[int]$seconds) $until=(Get-Date).AddSeconds($seconds); while(!(& $test)){ if($process.HasExited -or (Get-Date) -gt $until){return $false}; Start-Sleep -Milliseconds 200 }; $true}
    if(!(& $waitFor {(Test-Path -LiteralPath $log) -and (Select-String -LiteralPath $log -Pattern '^ready$' -Quiet)} 240)){$keyFailure='No ready line in keys.log'}
    if(!$keyFailure -and [ImpIdle]::ForegroundPid() -ne $process.Id){
        $process.Refresh()
        [void][ImpIdle]::SetForegroundWindow($process.MainWindowHandle)
        Start-Sleep -Milliseconds 500
        if([ImpIdle]::ForegroundPid() -ne $process.Id){$keyFailure="CMAA2 window not in front (foreground pid $([ImpIdle]::ForegroundPid())); no key sent"}
    }
    $index=0
    foreach($key in @(@{name='T';vk=0x54},@{name='Y';vk=0x59},@{name='F1';vk=0x70},@{name='Y';vk=0x59},@{name='F1';vk=0x70})){
        if($keyFailure){break}
        $index++
        if([ImpIdle]::ForegroundPid() -ne $process.Id){$keyFailure="Foreground changed before key $index ($($key.name)); no key sent";break}
        [ImpIdle]::Down([byte]$key.vk);Start-Sleep -Milliseconds 80;[ImpIdle]::Up([byte]$key.vk)
        $screen=Join-Path $output "screen_$index.png"
        if(!(& $waitFor {Test-Path -LiteralPath $screen} 30)){$keyFailure="No screen after key $index ($($key.name))";break}
        $keySteps+=[pscustomobject]@{key=$key.name;index=$index;sent_utc=[DateTime]::UtcNow.ToString('o')}
    }
}

$timedOut=-not $process.WaitForExit($TimeoutSeconds*1000)
if($timedOut){Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue;$process.WaitForExit()}
Start-Sleep -Milliseconds 500
$remaining=@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count
$failure=''
if($remaining -ne 0){$failure='CMAA2 process still running'}
elseif($timedOut){$failure="Timeout after $TimeoutSeconds s"}
elseif($keyFailure){$failure=$keyFailure}
elseif($process.ExitCode -ne 0){$failure="Exit code $($process.ExitCode)"}
$reports=@(Get-ChildItem -LiteralPath $autoBench -Recurse -File -Filter '*_results.csv' -ErrorAction SilentlyContinue | Where-Object {$before -notcontains $_.FullName})
$report=$null;$captureRoot=$null;$keyStates=$null
if(!$failure -and $Mode -eq 'Screens'){
    $captureRoot=$output
    $missing=@(300,330,360 | Where-Object {!(Test-Path -LiteralPath (Join-Path $output ('screen_{0:D3}.png' -f $_)))})
    if($missing.Count){$failure="Missing screens: $($missing -join ', ')"}
    if($reports.Count -ne 0){$failure="Unexpected AutoBench report in Screens mode"}
}
elseif(!$failure -and $Mode -eq 'DtRecord'){
    $captureRoot=$output
    $dtFile=Join-Path $output 'dt.csv'
    if(!(Test-Path -LiteralPath $dtFile)){$failure='No dt.csv'}
    elseif(@(Get-Content -LiteralPath $dtFile).Count -ne 1801){$failure='dt.csv does not have 1800 rows'}
    if($reports.Count -ne 0){$failure="Unexpected AutoBench report in DtRecord mode"}
}
elseif(!$failure -and $Mode -eq 'Keys'){
    $captureRoot=$output
    # State recorded with each screen: before any key, then after T, Y, F1, Y, F1.
    $at='aa=SMAA Adaptive + Temporal'
    $expected=@('aa=None temporal=1 selected=0 resources=0 presented=0 ui=1',
        "$at temporal=1 selected=1 resources=1 presented=1 ui=1","$at temporal=0 selected=0 resources=0 presented=0 ui=1",
        "$at temporal=0 selected=0 resources=0 presented=0 ui=0","$at temporal=1 selected=1 resources=1 presented=1 ui=0",
        "$at temporal=1 selected=1 resources=1 presented=1 ui=1")
    $lines=@(Get-Content -LiteralPath (Join-Path $output 'keys.log'))
    $keyStates=@(0..5 | ForEach-Object { $n=$_; $m=$lines | Where-Object {$_ -match "^screen $n frame \d+ (.*)$"} | Select-Object -First 1
        [pscustomobject]@{screen=$n;expected=$expected[$n];recorded=if($m){($m -replace '^screen \d+ frame \d+ ','')}else{$null};file_exists=(Test-Path -LiteralPath (Join-Path $output "screen_$n.png"))} })
    $bad=@($keyStates | Where-Object {$_.recorded -ne $_.expected -or !$_.file_exists})
    if($bad.Count){$failure="Key test state mismatch at screen $($bad[0].screen): $($bad[0].recorded)"}
    elseif(!($lines -contains 'done')){$failure='keys.log has no done line'}
    if($reports.Count -ne 0){$failure="Unexpected AutoBench report in Keys mode"}
}
elseif(!$failure){
    if($reports.Count -ne 1){$failure="Expected one new report, found $($reports.Count)"}
    else{
        $report=$reports[0].FullName
        $text=[System.IO.File]::ReadAllText($report)
        if($text -notmatch 'Aggregate: PASS' -or $text -match '(?im),\s*FAIL\s*(?:,|$)'){$failure="Report is not PASS: $report"}
        $captureRoot=([regex]::Match($text,'capture_root,\s*([^,\r\n]+)')).Groups[1].Value.Trim()
    }
}
$record=[pscustomobject]@{mode=$Mode;scene=$Scene;direction=$Direction;dt_csv=$DtCsv;label=$Label;result=if($failure){'FAIL'}else{'PASS'};failure=$failure;git_head=$head;renderer_dirty=$dirty;
    executable_sha256=$exeHash;idle_seconds_at_start=$idle;foreground_lock_timeout_ms=$lockTimeoutMs;gpu_before=$gpu;gpu_processes_before=$gpuProcesses;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o');
    exit_code=$process.ExitCode;remaining_cmaa2=$remaining;report=$report;report_sha256=if($report){(Get-FileHash -LiteralPath $report).Hash}else{$null};capture_root=$captureRoot;
    key_steps=$keySteps;key_states=$keyStates}
ConvertTo-Json -InputObject $record -Depth 4 | Set-Content -LiteralPath (Join-Path $output 'run.json') -Encoding utf8
if($failure){throw "Run failed: $failure"}
Write-Output "PASS: $captureRoot"
