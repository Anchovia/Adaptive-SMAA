param([int[]]$Cases=@(4,1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17))
$ErrorActionPreference='Stop'
$remeasureRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$remeasureBuild=Join-Path $remeasureRoot 'tmp/all-case-remeasurement'
$remeasurePlan=Get-Content -LiteralPath (Join-Path $remeasureBuild 'manifest.json') -Raw|ConvertFrom-Json
$remeasureSourceRoot=$remeasurePlan.source_root
$remeasureCaptureRoot='D:\SMAAResearchCaptures\all-cases-remeasurement-20261007'
if([IO.Path]::GetFullPath($remeasureCaptureRoot) -ne 'D:\SMAAResearchCaptures\all-cases-remeasurement-20261007'){throw 'Unexpected output root'}
$remeasureReceipts=Join-Path $remeasureBuild 'runs.json'
$remeasureRecords=@()
if(Test-Path -LiteralPath $remeasureReceipts){$remeasureRecords=@(Get-Content -LiteralPath $remeasureReceipts -Raw|ConvertFrom-Json)}
$remeasureMsbuild='C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe'
function Write-RemeasureState($Case,$Scene,$Phase,$Status){
    [pscustomobject]@{case=$Case;scene=$Scene;phase=$Phase;status=$Status;updated_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $remeasureBuild 'status.json') -Encoding utf8
    Write-Output "case=$Case scene=$Scene phase=$Phase status=$Status"
}
foreach($remeasureCase in $Cases){
    $remeasureItem=@($remeasurePlan.cases|Where-Object case -eq $remeasureCase)
    if($remeasureItem.Count -ne 1){throw 'Unknown case'}
    $remeasureItem=$remeasureItem[0];$remeasureSource=$remeasureItem.source
    if(![IO.Path]::GetFullPath($remeasureSource).StartsWith($remeasureSourceRoot+'\c',[StringComparison]::OrdinalIgnoreCase)){throw 'Source outside coordinator area'}
    if(@(Get-Process CMAA2 -ErrorAction SilentlyContinue).Count){throw 'Existing CMAA2 process'}
    foreach($remeasureLink in @(
        @{path=(Join-Path $remeasureSource '_Lib');target=(Join-Path $remeasureRoot '_Lib')},
        @{path=(Join-Path $remeasureSource 'Projects/CMAA2/Media');target=(Join-Path $remeasureRoot 'Projects/CMAA2/Media')}
    )){
        if(!(Test-Path -LiteralPath $remeasureLink.path)){New-Item -ItemType Junction -Path $remeasureLink.path -Target $remeasureLink.target|Out-Null}
        $remeasureNode=Get-Item -LiteralPath $remeasureLink.path -Force
        if($remeasureNode.LinkType -ne 'Junction' -or @($remeasureNode.Target)[0] -ne $remeasureLink.target){throw 'Shared input junction mismatch'}
    }
    # Backport only the process/completion wrapper; no renderer code is edited.
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'run_clean_cmaa2.ps1') -Destination (Join-Path $remeasureSource 'Tools/SMAA/run_clean_cmaa2.ps1') -Force
    Write-RemeasureState $remeasureCase '' 'Build' 'RUNNING'
    $remeasureBuildLog=Join-Path $remeasureBuild ("case$remeasureCase-build.log")
    & $remeasureMsbuild (Join-Path $remeasureSource 'Projects/CMAA2/CMAA2.vcxproj') /m:2 /p:Configuration=Release /p:Platform=x64 /p:BuildProjectReferences=false "/p:SolutionDir=$remeasureSource\" /v:minimal /nologo *> $remeasureBuildLog
    if($LASTEXITCODE -ne 0){Get-Content -LiteralPath $remeasureBuildLog -Tail 15;throw 'Build failed'}
    $remeasureExe=Join-Path $remeasureSource 'Projects/CMAA2/CMAA2.exe'
    $remeasureHash=(Get-FileHash -LiteralPath $remeasureExe).Hash
    foreach($remeasureScene in @('bistro','minecraft')){
        foreach($remeasurePhase in @('Smoke','Benchmark','Capture')){
            $remeasurePrevious=@($remeasureRecords|Where-Object {$_.case -eq $remeasureCase -and $_.scene -eq $remeasureScene -and $_.phase -eq $remeasurePhase})
            if($remeasurePrevious.Count){
                if($remeasurePrevious.Count -ne 1 -or $remeasurePrevious[0].executable_sha256 -ne $remeasureHash){throw 'Completed run has a different binary'}
                if((Get-FileHash -LiteralPath $remeasurePrevious[0].report).Hash -ne $remeasurePrevious[0].report_sha256){throw 'Saved report changed'}
                Write-RemeasureState $remeasureCase $remeasureScene $remeasurePhase 'ALREADY COMPLETE';continue
            }
            if($remeasurePhase -eq 'Benchmark' -and !@($remeasureRecords|Where-Object {$_.case -eq $remeasureCase -and $_.scene -eq $remeasureScene -and $_.phase -eq 'Smoke' -and $_.executable_sha256 -eq $remeasureHash}).Count){throw 'Smoke required'}
            foreach($remeasureShader in $remeasureItem.production_sha256.PSObject.Properties){
                if((Get-FileHash -LiteralPath (Join-Path $remeasureSource $remeasureShader.Name)).Hash -ne $remeasureShader.Value){throw 'Archived production code changed'}
            }
            $remeasureSettings=Join-Path $remeasureSource 'Projects/CMAA2/ApplicationSettings.xml'
            $remeasureXml=[IO.File]::ReadAllText($remeasureSettings)
            $remeasureSceneIndex=if($remeasureScene -eq 'bistro'){0}else{2}
            $remeasureXml=[regex]::Replace($remeasureXml,'<SceneChoice>\d+</SceneChoice>',"<SceneChoice>$remeasureSceneIndex</SceneChoice>")
            $remeasureXml=[regex]::Replace($remeasureXml,'<CurrentAAOption>\d+</CurrentAAOption>','<CurrentAAOption>0</CurrentAAOption>')
            [IO.File]::WriteAllText($remeasureSettings,$remeasureXml)
            $remeasureOutput=Join-Path $remeasureCaptureRoot ("case$remeasureCase")
            $remeasureArgs=@(($remeasureItem.command+$remeasurePhase),$remeasureScene,$remeasureOutput)
            $remeasureStarted=[DateTime]::UtcNow.ToString('o')
            Write-RemeasureState $remeasureCase $remeasureScene $remeasurePhase 'RUNNING'
            $remeasureResult=& (Join-Path $remeasureSource 'Tools/SMAA/run_clean_cmaa2.ps1') -CMAA2Arguments $remeasureArgs -Hidden -TimeoutSeconds 1200
            $remeasurePass=$remeasureResult|Where-Object {$_ -match 'PASS:.*report='}|Select-Object -Last 1
            if(!$remeasurePass){throw 'No completed result'}
            $remeasureReport=($remeasurePass -split 'report=',2)[1].Trim()
            if((Get-Content -LiteralPath $remeasureReport -Raw) -notmatch 'Aggregate: PASS'){throw 'Aggregate missing'}
            if((Get-FileHash -LiteralPath $remeasureExe).Hash -ne $remeasureHash){throw 'Executable changed during run'}
            $remeasureRecords += [pscustomobject]@{case=$remeasureCase;branch=$remeasureItem.branch;commit=$remeasureItem.commit;scene=$remeasureScene;phase=$remeasurePhase;arguments=$remeasureArgs;window='hidden';started_utc=$remeasureStarted;completed_utc=[DateTime]::UtcNow.ToString('o');executable_sha256=$remeasureHash;report=$remeasureReport;report_sha256=(Get-FileHash -LiteralPath $remeasureReport).Hash}
            ConvertTo-Json -InputObject @($remeasureRecords) -Depth 6|Set-Content -LiteralPath $remeasureReceipts -Encoding utf8
            Write-RemeasureState $remeasureCase $remeasureScene $remeasurePhase 'PASS'
        }
    }
}
Write-RemeasureState 0 '' 'All' 'PASS'
