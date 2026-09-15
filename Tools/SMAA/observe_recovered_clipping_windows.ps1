# Read-only window observations during the paired benchmark; does not activate windows.
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$manifest=Join-Path $repo 'tmp/recovered-clipping/runs.json'
$output=Join-Path $repo 'tmp/recovered-clipping/windows.json'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ClippingWindowState {
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hwnd);
}
'@
$samples=@();$start=Get-Date
while(((Get-Date)-$start).TotalMinutes -lt 30) {
    foreach($p in @(Get-Process CMAA2 -ErrorAction SilentlyContinue)) {
        $handle=$p.MainWindowHandle
        if($handle -ne [IntPtr]::Zero) {
            $samples+=[ordered]@{utc=(Get-Date).ToUniversalTime().ToString('o');process_id=$p.Id;
                visible=[ClippingWindowState]::IsWindowVisible($handle);minimized=[ClippingWindowState]::IsIconic($handle)}
        }
    }
    # The writer replaces the manifest at each completed run; retry a partial read.
    try {$runs=@(Get-Content -Raw $manifest | ConvertFrom-Json)} catch {Start-Sleep -Seconds 2;continue}
    $complete=@($runs | Where-Object {$_.mode-eq 'Benchmark' -and $_.status-eq 'PASS'})
    if($complete.Count-eq 12) {
        foreach($r in $complete) {
            $found=@($samples | Where-Object {$_.process_id-eq $r.process_id})
            if($found.Count-eq 0 -or @($found | Where-Object {-not $_.visible -or $_.minimized}).Count-ne 0) {
                ConvertTo-Json -Depth 5 -InputObject @($samples) | Set-Content $output -Encoding utf8
                throw "Window-state observation failed for $($r.label)"
            }
        }
        ConvertTo-Json -Depth 5 -InputObject @($samples) | Set-Content $output -Encoding utf8
        Write-Output 'PASS: all 12 benchmark processes observed visible and not minimized'
        exit 0
    }
    Start-Sleep -Seconds 2
}
ConvertTo-Json -Depth 5 -InputObject @($samples) | Set-Content $output -Encoding utf8
throw 'Window observation timed out before twelve completed benchmark runs'
