param(
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][ValidateSet('Plan','Apply','Verify')][string]$Phase
)
$ErrorActionPreference = 'Stop'
function Get-SmaaCleanupHash([string]$Path) { $stream=[IO.File]::OpenRead($Path); try { [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)) } finally { $stream.Dispose() } }
$smaaConfig = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$smaaRawStage = $smaaConfig.stage_id -eq 'explicitly_authorized_old_raw_captures'
if ($smaaRawStage) {
    $smaaExactRoots = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($smaaExpectedRoot in @('D:\SMAAResearchCaptures','D:\SMAA-Research-Data\AutoBench','C:\Users\USER\Desktop\research\tmp\worktrees\standard-t2x-reuse\Projects\CMAA2\AutoBench')) { [void]$smaaExactRoots.Add($smaaExpectedRoot) }
    $smaaConfiguredRoots = [string[]]@($smaaConfig.roots | ForEach-Object { [IO.Path]::GetFullPath($_.path).TrimEnd('\') })
    if ($smaaConfiguredRoots.Count -ne 3 -or -not $smaaExactRoots.SetEquals($smaaConfiguredRoots) -or
        [long]$smaaConfig.cutoff_utc_ticks -ne 639270684000000000 -or $smaaConfig.user_approved -ne $true -or
        [string]::IsNullOrWhiteSpace($smaaConfig.user_authorization)) { throw 'Raw cleanup requires explicit authorization for exactly three roots and the fixed 2026-10-09 KST cutoff' }
}
elseif ($smaaConfig.stage_id -ne 'conventional_old_generated_media' -or $smaaConfig.roots.Count -gt 6 -or -not $smaaConfig.cutoff_utc_ticks) { throw 'Requires dated conventional-media-only scope' }
$smaaAuditRoot = [IO.Path]::GetFullPath($smaaConfig.audit_root)
$smaaPlanPath = Join-Path $smaaAuditRoot 'deletion-plan.tsv'
$smaaKeepAudit = Get-Content -LiteralPath (Join-Path $smaaAuditRoot 'preservation-audit.json') -Raw | ConvertFrom-Json
if ($smaaKeepAudit.validation -ne 'PASS' -or $smaaKeepAudit.files.Count -ne 58) { throw 'Preservation prerequisite failed' }
if ((Get-Process -Name CMAA2 -ErrorAction SilentlyContinue)) { throw 'CMAA2 is running; no cleanup' }

Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

public static class ResearchMediaCleanup {
    private static HashSet<string> Extensions = new HashSet<string>(StringComparer.OrdinalIgnoreCase) {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".avif",
        ".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv"
    };
    public static long MaxWriteTicks = DateTime.MaxValue.Ticks;
    public static void UseExplicitRawScope() {
        Extensions = new HashSet<string>(new string[]{".png", ".dds", ".rg8", ".rdc"}, StringComparer.OrdinalIgnoreCase);
    }
    private static HashSet<string> TempSourceFolders = new HashSet<string>(StringComparer.OrdinalIgnoreCase) {
        "Projects", "Modules", "Media", "Scenes", "Textures", "Assets", "vendor", "third_party",
        "node_modules", ".research-tools", ".git", "r17", "worktrees"
    };
    private static string Norm(string p) { return Path.GetFullPath(p).TrimEnd(Path.DirectorySeparatorChar); }
    private static bool Under(string p, string root) {
        return p.Equals(root, StringComparison.OrdinalIgnoreCase) ||
            p.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    }
    private static bool Protected(string p, HashSet<string> files, string[] prefixes) {
        if (files.Contains(p)) return true;
        foreach (string q in prefixes) if (Under(p, Norm(q))) return true;
        return false;
    }
    public static long[] Plan(string[] roots, string[] kinds, string[] protectedFiles,
            string[] protectedPrefixes, string output) {
        var excluded = new HashSet<string>(protectedFiles, StringComparer.OrdinalIgnoreCase);
        long files=0, bytes=0, retained=0, dirs=0;
        using (var writer = new StreamWriter(output, false, new UTF8Encoding(false))) {
            writer.WriteLine("absolute_path\tbytes\tlast_write_utc_ticks\tverified_root");
            for (int i=0; i<roots.Length; i++) {
                string root=Norm(roots[i]);
                if (!Directory.Exists(root)) continue;
                var rootInfo=new DirectoryInfo(root);
                if ((rootInfo.Attributes & FileAttributes.ReparsePoint)!=0) throw new Exception("Unresolved root: " + root);
                var stack=new Stack<DirectoryInfo>(); stack.Push(rootInfo);
                long start=files;
                while(stack.Count>0) {
                    DirectoryInfo dir=stack.Pop();
                    if (!Under(dir.FullName,root)) throw new Exception("Directory escaped root");
                    if (Protected(dir.FullName,excluded,protectedPrefixes)) continue;
                    dirs++;
                    foreach(FileSystemInfo info in dir.EnumerateFileSystemInfos()) {
                        FileAttributes attr=info.Attributes;
                        if ((attr & FileAttributes.ReparsePoint)!=0) { retained++; continue; }
                        if (Protected(info.FullName,excluded,protectedPrefixes)) { retained++; continue; }
                        if ((attr & FileAttributes.Directory)!=0) {
                            if (info.Name.Equals(".git",StringComparison.OrdinalIgnoreCase)) continue;
                            if (kinds[i]=="TempDiagnostic" &&
                                (TempSourceFolders.Contains(info.Name) ||
                                 info.Name.StartsWith("tscmaa-source",StringComparison.OrdinalIgnoreCase) ||
                                 info.Name.StartsWith("storage-",StringComparison.OrdinalIgnoreCase) ||
                                 info.Name.StartsWith("disk-cleanup",StringComparison.OrdinalIgnoreCase))) continue;
                            stack.Push((DirectoryInfo)info); continue;
                        }
                        if (!Extensions.Contains(Path.GetExtension(info.Name)) || info.LastWriteTimeUtc.Ticks>=MaxWriteTicks) { retained++; continue; }
                        string path=Norm(info.FullName);
                        if (!Under(path,root) || path.IndexOfAny(new char[]{'\t','\r','\n'})>=0) throw new Exception("Invalid candidate path");
                        var file=(FileInfo)info;
                        writer.WriteLine(path+"\t"+file.Length.ToString(CultureInfo.InvariantCulture)+"\t"+
                            file.LastWriteTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture)+"\t"+root);
                        files++; bytes+=file.Length;
                    }
                    if (dirs%1000==0) { writer.Flush(); Console.WriteLine("PLAN directories="+dirs+" candidate_files="+files); }
                }
                writer.Flush(); Console.WriteLine("PLAN ROOT "+root+" candidate_files="+(files-start));
            }
        }
        return new long[]{files,bytes,retained,dirs};
    }
    public static long[] Apply(string plan, string[] roots, string[] protectedFiles,
            string[] protectedPrefixes, string successPath, string failurePath) {
        var allowed=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach(string r in roots) allowed.Add(Norm(r));
        var excluded=new HashSet<string>(protectedFiles,StringComparer.OrdinalIgnoreCase);
        long deleted=0,bytes=0,missing=0,errors=0;
        var checkedDirectories=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        using(var success=new StreamWriter(successPath,false,new UTF8Encoding(false)))
        using(var failure=new StreamWriter(failurePath,false,new UTF8Encoding(false))) {
            foreach(string line in File.ReadLines(plan)) {
                if(line.StartsWith("absolute_path\t")) continue;
                string[] parts=line.Split('\t'); if(parts.Length!=4) throw new Exception("Invalid plan row");
                string path=Norm(parts[0]), root=Norm(parts[3]);
                if(!allowed.Contains(root) || !Under(path,root) || !Extensions.Contains(Path.GetExtension(path)) ||
                    Protected(path,excluded,protectedPrefixes) || long.Parse(parts[2],CultureInfo.InvariantCulture)>=MaxWriteTicks) throw new Exception("Deletion scope validation failed: "+path);
                try {
                    if(!File.Exists(path)) { missing++; continue; }
                    var f=new FileInfo(path);
                    if((f.Attributes & FileAttributes.ReparsePoint)!=0) throw new Exception("Reparse file");
                    if(f.Length!=long.Parse(parts[1],CultureInfo.InvariantCulture) ||
                       f.LastWriteTimeUtc.Ticks!=long.Parse(parts[2],CultureInfo.InvariantCulture)) throw new Exception("File changed since plan");
                    DirectoryInfo parent=f.Directory;
                    while(parent!=null && Under(parent.FullName,root) && !checkedDirectories.Contains(parent.FullName)) {
                        if((parent.Attributes & FileAttributes.ReparsePoint)!=0) throw new Exception("Reparse ancestor");
                        checkedDirectories.Add(parent.FullName);
                        if(parent.FullName.Equals(root,StringComparison.OrdinalIgnoreCase)) break;
                        parent=parent.Parent;
                    }
                    File.Delete(path);
                    if(File.Exists(path)) throw new Exception("File still exists after delete");
                    success.WriteLine(line); deleted++; bytes+=long.Parse(parts[1],CultureInfo.InvariantCulture);
                } catch(Exception ex) {
                    failure.WriteLine(path+"\t"+ex.GetType().Name+"\t"+ex.Message.Replace('\t',' ').Replace('\r',' ').Replace('\n',' ')); errors++;
                }
                if((deleted+errors+missing)%10000==0) {
                    success.Flush(); failure.Flush(); Console.WriteLine("DELETE files="+deleted+" logical_GiB="+(bytes/1073741824.0).ToString("F2")+" errors="+errors);
                }
            }
        }
        return new long[]{deleted,bytes,missing,errors};
    }
    public static long[] Verify(string plan) {
        long missing=0,present=0;
        foreach(string line in File.ReadLines(plan)) {
            if(line.StartsWith("absolute_path\t")) continue;
            string[] parts=line.Split('\t'); if(File.Exists(parts[0])) present++; else missing++;
        }
        return new long[]{missing,present};
    }
    public static long SnapshotRetained(string[] roots, string[] protectedFiles, string[] protectedPrefixes, string output) {
        var excluded=new HashSet<string>(protectedFiles,StringComparer.OrdinalIgnoreCase);
        long files=0;
        using(var writer=new StreamWriter(output,false,new UTF8Encoding(false))) {
            writer.WriteLine("absolute_path\tbytes\tlast_write_utc_ticks");
            foreach(string r in roots) {
                string root=Norm(r);
                if(!Directory.Exists(root)) throw new Exception("Missing root: "+root);
                var stack=new Stack<DirectoryInfo>(); stack.Push(new DirectoryInfo(root));
                while(stack.Count>0) {
                    var dir=stack.Pop();
                    foreach(var info in dir.EnumerateFileSystemInfos()) {
                        if((info.Attributes & FileAttributes.ReparsePoint)!=0) continue;
                        if((info.Attributes & FileAttributes.Directory)!=0) {
                            if(!info.Name.Equals(".git",StringComparison.OrdinalIgnoreCase)) stack.Push((DirectoryInfo)info);
                            continue;
                        }
                        string path=Norm(info.FullName);
                        if(!Under(path,root)) throw new Exception("Retention path escaped root");
                        if(Extensions.Contains(Path.GetExtension(path)) && info.LastWriteTimeUtc.Ticks<MaxWriteTicks &&
                           !Protected(path,excluded,protectedPrefixes)) continue;
                        if(path.IndexOfAny(new char[]{'\t','\r','\n'})>=0) throw new Exception("Invalid retention path");
                        var f=(FileInfo)info;
                        writer.WriteLine(path+"\t"+f.Length.ToString(CultureInfo.InvariantCulture)+"\t"+f.LastWriteTimeUtc.Ticks.ToString(CultureInfo.InvariantCulture)); files++;
                    }
                }
            }
        }
        return files;
    }
    public static long[] VerifyRetained(string snapshot) {
        long unchanged=0,missing=0,changed=0;
        foreach(string line in File.ReadLines(snapshot)) {
            if(line.StartsWith("absolute_path\t")) continue;
            string[] parts=line.Split('\t'); if(parts.Length!=3) throw new Exception("Invalid retention row");
            if(!File.Exists(parts[0])) { missing++; continue; }
            var f=new FileInfo(parts[0]);
            if(f.Length!=long.Parse(parts[1],CultureInfo.InvariantCulture) || f.LastWriteTimeUtc.Ticks!=long.Parse(parts[2],CultureInfo.InvariantCulture)) changed++;
            else unchanged++;
        }
        return new long[]{unchanged,missing,changed};
    }
}
'@

[ResearchMediaCleanup]::MaxWriteTicks=[long]$smaaConfig.cutoff_utc_ticks
if ($smaaRawStage) { [ResearchMediaCleanup]::UseExplicitRawScope() }
$smaaRoots = [string[]]@($smaaConfig.roots | ForEach-Object { $_.path })
$smaaKinds = [string[]]@($smaaConfig.roots | ForEach-Object { $_.kind })
$smaaProtectedFiles = [string[]]@($smaaConfig.protected_files)
$smaaProtectedPrefixes = [string[]]@($smaaConfig.protected_prefixes)
foreach ($smaaRoot in $smaaRoots) {
    $smaaAbsolute = [IO.Path]::GetFullPath($smaaRoot)
    $smaaAllowedWorkspace = $smaaAbsolute.StartsWith('C:\Users\USER\Desktop\research\',[StringComparison]::OrdinalIgnoreCase)
    $smaaAllowedCaptures = $smaaAbsolute -eq 'D:\SMAAResearchCaptures'
    $smaaAllowedAutoBench = $smaaAbsolute -eq 'D:\SMAA-Research-Data\AutoBench'
    if (-not ($smaaAllowedWorkspace -or $smaaAllowedCaptures -or $smaaAllowedAutoBench)) { throw "Invalid approved root: $smaaRoot" }
    if ((Get-Item -LiteralPath $smaaRoot).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Unresolved root: $smaaRoot" }
}

if ($Phase -eq 'Plan') {
    $smaaCounts = [ResearchMediaCleanup]::Plan($smaaRoots,$smaaKinds,$smaaProtectedFiles,$smaaProtectedPrefixes,$smaaPlanPath)
    $smaaRetentionCount = $null
    if ($smaaRawStage) { $smaaRetentionCount=[ResearchMediaCleanup]::SnapshotRetained($smaaRoots,$smaaProtectedFiles,$smaaProtectedPrefixes,(Join-Path $smaaAuditRoot 'retained-files.tsv')) }
    [pscustomobject]@{ files=$smaaCounts[0]; logical_bytes=$smaaCounts[1]; retained_files=$smaaCounts[2]; retained_snapshot_files=$smaaRetentionCount; directories=$smaaCounts[3]; plan_sha256=(Get-SmaaCleanupHash $smaaPlanPath); roots=$smaaConfig.roots; stage_id=$smaaConfig.stage_id } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $smaaAuditRoot 'plan-summary.json') -Encoding utf8
    "PLAN COMPLETE files=$($smaaCounts[0]) logical_GiB=$([math]::Round($smaaCounts[1]/1GB,2))"
}
elseif ($Phase -eq 'Apply') {
    $smaaSummary = Get-Content -LiteralPath (Join-Path $smaaAuditRoot 'plan-summary.json') -Raw | ConvertFrom-Json
    if ((Get-SmaaCleanupHash $smaaPlanPath) -ne $smaaSummary.plan_sha256) { throw 'Plan has changed' }
    foreach ($smaaFile in $smaaKeepAudit.files) {
        if ((Get-SmaaCleanupHash $smaaFile.destination) -ne $smaaFile.sha256) { throw 'Minimal archive changed' }
    }
    $smaaFreeBefore = @{}; foreach ($smaaDrive in @('C','D')) { $smaaFreeBefore[$smaaDrive]=([IO.DriveInfo]::new($smaaDrive + ':')).AvailableFreeSpace }
    $smaaCounts = [ResearchMediaCleanup]::Apply($smaaPlanPath,$smaaRoots,$smaaProtectedFiles,$smaaProtectedPrefixes,(Join-Path $smaaAuditRoot 'deleted-files.tsv'),(Join-Path $smaaAuditRoot 'failed-files.tsv'))
    $smaaFree = @{}; foreach ($smaaDrive in @('C','D')) { $smaaFree[$smaaDrive]=([IO.DriveInfo]::new($smaaDrive + ':')).AvailableFreeSpace }
    [pscustomobject]@{ deleted_files=$smaaCounts[0]; logical_deleted_bytes=$smaaCounts[1]; already_missing=$smaaCounts[2]; errors=$smaaCounts[3]; free_bytes_after=$smaaFree; free_bytes_before=$smaaFreeBefore; stage_id=$smaaConfig.stage_id; note='Logical deleted bytes include hardlink aliases. Actual free-space change is reported separately.' } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $smaaAuditRoot 'deletion-summary.json') -Encoding utf8
    "DELETE COMPLETE files=$($smaaCounts[0]) errors=$($smaaCounts[3])"
}
else {
    $smaaCounts=[ResearchMediaCleanup]::Verify($smaaPlanPath)
    foreach ($smaaFile in $smaaKeepAudit.files) {
        if ((Get-SmaaCleanupHash $smaaFile.destination) -ne $smaaFile.sha256) { throw 'Preserved media changed' }
    }
    $smaaRetention = $null
    if ($smaaRawStage) { $smaaRetention=[ResearchMediaCleanup]::VerifyRetained((Join-Path $smaaAuditRoot 'retained-files.tsv')); if ($smaaRetention[1] -ne 0 -or $smaaRetention[2] -ne 0) { throw "Retention validation failed: $smaaRetention" } }
    [pscustomobject]@{ missing_planned_media=$smaaCounts[0]; remaining_planned_media=$smaaCounts[1]; preserved_files=58; preserved_hashes='PASS'; retained_unchanged=$(if ($smaaRetention) { $smaaRetention[0] } else { $null }); retained_missing=$(if ($smaaRetention) { $smaaRetention[1] } else { $null }); retained_changed=$(if ($smaaRetention) { $smaaRetention[2] } else { $null }) } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $smaaAuditRoot 'verification.json') -Encoding utf8
    "VERIFY COMPLETE remaining=$($smaaCounts[1]) preservation=PASS"
}
