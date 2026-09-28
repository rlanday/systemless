param(
 [Parameter(Mandatory=$true)][string]$Run,
 [Parameter(Mandatory=$true)][string]$Binary,
 [int[]]$Ticks=@(1720,3500,4500),
 [ValidateSet("public","off","absent")][string]$Mode="absent",
 [switch]$Diagnostics,
 # Correctness only: skip the AC-power guard; cpu_seconds is then not a timing result.
 [switch]$ExactnessOnly,
 [string]$InputScript='',
 [string]$Archive='<EV_ARCHIVE_DIR>\EV_Override_1.0.1.sit'
)
$ErrorActionPreference='Stop'
if(!$InputScript){$InputScript=Join-Path $PSScriptRoot 'ev-scalar-flight-input.txt'}
if([IO.Path]::GetFileName($Run) -ne $Run){throw 'Run must be one directory name'}
$exe=(Resolve-Path -LiteralPath $Binary).ProviderPath
$sourceArchive=(Resolve-Path -LiteralPath $Archive).ProviderPath
$sourceInput=(Resolve-Path -LiteralPath $InputScript).ProviderPath
$out=Join-Path $PSScriptRoot $Run
if(Test-Path -LiteralPath $out){throw 'Run already exists'}
if(@($Ticks|Where-Object {$_ -le 0}).Count){throw 'Ticks must be positive'}
if(@($Ticks|Select-Object -Unique).Count -ne $Ticks.Count){throw 'Duplicate checkpoints'}
New-Item -ItemType Directory -Path $out | Out-Null
Copy-Item -LiteralPath $sourceInput -Destination (Join-Path $out 'frozen-input.txt')
$inputLines=@(Get-Content -LiteralPath (Join-Path $out 'frozen-input.txt'))
$utf8=New-Object System.Text.UTF8Encoding($false)
$exeHash=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$manifestPath=Join-Path $PSScriptRoot ([IO.Path]::GetFileName($exe) -replace '\.exe$','-manifest.json')
if(!(Test-Path -LiteralPath $manifestPath)){
 # Plain cargo builds have no frozen manifest: record the binary's hash so the check below still binds the run to it.
 @{exe_sha256=$exeHash;scope='plain cargo build (no frozen build manifest)';binary=[IO.Path]::GetFileName($exe)}|ConvertTo-Json|Set-Content -LiteralPath $manifestPath
}
$manifest=Get-Content -Raw $manifestPath|ConvertFrom-Json
if($exeHash -ne $manifest.exe_sha256){throw 'Wrong frontend binary'}
Copy-Item $manifestPath (Join-Path $out 'build-manifest.json')
Copy-Item $PSCommandPath (Join-Path $out 'runner.ps1')
$archiveHash=(Get-FileHash -LiteralPath $sourceArchive -Algorithm SHA256).Hash.ToLowerInvariant()
$inputHash=(Get-FileHash -LiteralPath (Join-Path $out 'frozen-input.txt') -Algorithm SHA256).Hash.ToLowerInvariant()
foreach($tickCount in $Ticks){
 $stage=Join-Path $out "ticks-$tickCount"
 New-Item -ItemType Directory -Path $stage | Out-Null
 # Each checkpoint is a fresh replay. No user saves or previous checkpoint's
 # pilot are imported. Every directory removed below was created here.
 $local=Join-Path ([IO.Path]::GetTempPath()) ('SystemlessEvScalar-'+[Guid]::NewGuid().ToString('N'))
 New-Item -ItemType Directory -Path $local | Out-Null
 [IO.File]::WriteAllText((Join-Path $local 'owned-by-validation.txt'),$Run,$utf8)
 $complete=$false
 $process=$null
 $stdoutTask=$null;$stderrTask=$null;$memoryRows=$null;$replayClock=$null
 try {
  $game=Join-Path $local 'EV_Override_1.0.1.sit'
  Copy-Item -LiteralPath $sourceArchive -Destination $game
  $selected=New-Object 'System.Collections.Generic.List[string]'
  $expectedEvents=0
  foreach($line in $inputLines){
   $body=($line -split '#',2)[0].Trim()
   if(!$body){continue}
   $parts=$body -split '\s+'
   if([int]$parts[0] -ge $tickCount){continue}
   $selected.Add($body)
   $expectedEvents+=if($parts[1] -in @('press','click')){2}else{1}
  }
  $localInput=Join-Path $local 'input.txt'
  [IO.File]::WriteAllLines($localInput,$selected,$utf8)
  Copy-Item -LiteralPath $localInput -Destination (Join-Path $stage 'input.txt')
  $psi=New-Object Diagnostics.ProcessStartInfo
  $psi.FileName=$exe
  $psi.Arguments='--headless --max-ticks '+$tickCount+' --headless-start-time 3871497600 --tick-input-script "'+$localInput+'" "'+$game+'"'
  $psi.WorkingDirectory=$local
  $psi.UseShellExecute=$false
  $psi.CreateNoWindow=$true
  $psi.RedirectStandardOutput=$true
  $psi.RedirectStandardError=$true
  foreach($key in @($psi.EnvironmentVariables.Keys)){
   if($key -like 'SYSTEMLESS_*' -or $key -like 'M68K_*' -or $key -eq 'PROFILE_FIRE'){$psi.EnvironmentVariables.Remove($key)}
  }
  # std::env::temp_dir selects this private screenshot location on Windows.
  # Child-only environment: the shell's TEMP and TMP are not changed.
  $psi.EnvironmentVariables['TEMP']=$local
  $psi.EnvironmentVariables['TMP']=$local
  if($Diagnostics){$psi.EnvironmentVariables['SYSTEMLESS_HEADLESS_TIME_TRACE']='1'}
  if($Mode -ne 'absent'){$psi.EnvironmentVariables['M68K_NATIVE_REGIONS']=$Mode}
  if($Diagnostics){$psi.EnvironmentVariables['M68K_NATIVE_REGION_DIAGNOSTICS']='1'}
  $powerBefore=(& (Join-Path $PSScriptRoot 'power-state.ps1')|ConvertFrom-Json)
  if(!$ExactnessOnly -and $powerBefore.ac_line_status -ne 1){throw 'Timing requires AC power; the source changed or the laptop is on battery'}
  $started=[DateTime]::UtcNow.ToString('o')
  $backgroundBefore=@{}
  foreach($bp in @(Get-Process -ErrorAction SilentlyContinue)){
   try {$backgroundBefore[$bp.Id]=@{name=$bp.ProcessName;start=$bp.StartTime;cpu=$bp.TotalProcessorTime.TotalSeconds}}catch{}
  }
  $backgroundClock=[Diagnostics.Stopwatch]::StartNew()
  $process=New-Object Diagnostics.Process
  $process.StartInfo=$psi
  if(!$process.Start()){throw 'Failed to start owned replay process'}
  $stdoutTask=$process.StandardOutput.ReadToEndAsync()
  $stderrTask=$process.StandardError.ReadToEndAsync()
  $sampledPeakWs=0L; $sampledPeakPrivate=0L; $memorySamples=0
  $replayClock=[Diagnostics.Stopwatch]::StartNew()
  @{start_utc=$started;power_before=$powerBefore;timeout_seconds=300;clock='Stopwatch monotonic';qpc=[Diagnostics.Stopwatch]::GetTimestamp();frequency=[Diagnostics.Stopwatch]::Frequency}|ConvertTo-Json -Depth 5|Set-Content (Join-Path $stage 'preflight.json')
  $memoryRows=New-Object System.Collections.Generic.List[object]
  while(-not $process.WaitForExit(100)){
   if($replayClock.Elapsed.TotalSeconds -gt 300){$process.Kill();$process.WaitForExit();throw 'Owned replay exceeded300seconds (monotonic)'}
   try {
    $process.Refresh()
    $sampledPeakWs=[Math]::Max($sampledPeakWs,$process.WorkingSet64)
    $sampledPeakPrivate=[Math]::Max($sampledPeakPrivate,$process.PrivateMemorySize64)
    $memorySamples++
    $memoryRows.Add([pscustomobject]@{elapsed_seconds=$replayClock.Elapsed.TotalSeconds;working_set_bytes=$process.WorkingSet64;private_bytes=$process.PrivateMemorySize64})
   }catch{}
  }
  $replayClock.Stop()
  $backgroundWall=$backgroundClock.Elapsed.TotalSeconds
  $background=@(foreach($bp in @(Get-Process -ErrorAction SilentlyContinue)){
   try {
    $old=$backgroundBefore[$bp.Id]
    if($null -ne $old -and $old.name -eq $bp.ProcessName -and $old.start -eq $bp.StartTime -and $bp.Id -ne $process.Id){
     $delta=$bp.TotalProcessorTime.TotalSeconds-$old.cpu
     if($delta -gt 0){[pscustomobject]@{name=$bp.ProcessName;cpu_seconds=$delta;one_core_percent=100*$delta/$backgroundWall}}
    }
   }catch{}
  })
  @{wall_seconds=$backgroundWall;top=@($background|Sort-Object cpu_seconds -Descending|Select-Object -First 12)}|ConvertTo-Json -Depth 5|Set-Content (Join-Path $stage 'background-cpu.json')
  $memoryRows|Export-Csv -NoTypeInformation (Join-Path $stage 'memory.csv')
  $stdout=$stdoutTask.GetAwaiter().GetResult()
  $stderr=$stderrTask.GetAwaiter().GetResult()
  [IO.File]::WriteAllText((Join-Path $stage 'stdout.log'),$stdout,$utf8)
  [IO.File]::WriteAllText((Join-Path $stage 'stderr.log'),$stderr,$utf8)
  if($process.ExitCode -ne 0){throw "Replay exited $($process.ExitCode)"}
  $lines=@($stderr -split '\r?\n')
  $completion=@($lines|Where-Object {$_ -match '^\[HEADLESS-TIME\] complete '})
  if($completion.Count -ne 1){throw 'Missing or duplicate completion record'}
  if($completion[0] -notmatch "frontend_ticks=$tickCount\b" -or $completion[0] -notmatch "input_events=$expectedEvents\b"){
   throw 'Incomplete frontend ticks or input delivery'
  }
  $stateLines=@($lines|Where-Object {$_ -match '^\[HEADLESS-TIME(?:-TRACE)?\] (?:start |input |complete |frontend=)'})
  [IO.File]::WriteAllText((Join-Path $stage 'state-lines.txt'),(($stateLines -join "`n")+"`n"),$utf8)
  $screenshot=Join-Path $local 'systemless_headless_9999.png'
  if(!(Test-Path -LiteralPath $screenshot)){throw 'Private final screenshot missing'}
  Copy-Item -LiteralPath $screenshot -Destination (Join-Path $stage 'final.png')
  $saveManifest=@()
  $saves=Join-Path $local '.systemless'
  if(Test-Path -LiteralPath $saves){
   $saveManifest=@(Get-ChildItem -LiteralPath $saves -File -Recurse -Force|Sort-Object FullName|ForEach-Object {
    [ordered]@{path=$_.FullName.Substring($saves.Length).TrimStart('\');bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
   })
   Copy-Item -LiteralPath $saves -Destination (Join-Path $stage 'saves') -Recurse -Force
  }
  [IO.File]::WriteAllText((Join-Path $stage 'save-manifest.json'),(ConvertTo-Json -InputObject @($saveManifest) -Depth 5),$utf8)
  $metrics=[ordered]@{
   scope='Hidden fixed-work EV replay; CPU includes all threads. Sampled memory at100ms can miss short peaks; no GUI/input latency claim'
   diagnostics=[bool]$Diagnostics;sampled_peak_ws_bytes=$sampledPeakWs;sampled_peak_private_bytes=$sampledPeakPrivate;memory_samples=$memorySamples
   binary=$exe;binary_sha256=$exeHash;archive_sha256=$archiveHash;input_sha256=$inputHash
   native_region_mode=$Mode;ticks=$tickCount;expected_input_events=$expectedEvents;completion=$completion[0]
   trace_records=@($lines|Where-Object {$_ -match '^\[HEADLESS-TIME-TRACE\] '}).Count
   image_sha256=(Get-FileHash -LiteralPath (Join-Path $stage 'final.png') -Algorithm SHA256).Hash.ToLowerInvariant()
   state_sha256=(Get-FileHash -LiteralPath (Join-Path $stage 'state-lines.txt') -Algorithm SHA256).Hash.ToLowerInvariant()
   visual_flight_verified=$false;exit_code=$process.ExitCode
   cpu_seconds=$process.TotalProcessorTime.TotalSeconds;wall_seconds=$replayClock.Elapsed.TotalSeconds;wall_clock='monotonic Stopwatch observed process completion (100ms poll)'
   exactness_only=[bool]$ExactnessOnly;start_utc=$started;end_utc=[DateTime]::UtcNow.ToString('o');power_before=$powerBefore
   power_after=(& (Join-Path $PSScriptRoot 'power-state.ps1')|ConvertFrom-Json)
  }
  $metrics|ConvertTo-Json -Depth 7|Set-Content -LiteralPath (Join-Path $stage 'result.json')
  $complete=$true
  Write-Output "$Run checkpoint$tickCount completed; inspect $stage\final.png to identify scene"
 } catch {
  $failure=$_
  if($null -ne $process){try {if(-not $process.HasExited){$process.Kill();[void]$process.WaitForExit(10000)}}catch{}}
  foreach($entry in @(@('stdout.log',$stdoutTask),@('stderr.log',$stderrTask))){
   try {if($null -ne $entry[1] -and $entry[1].Wait(5000)){[IO.File]::WriteAllText((Join-Path $stage $entry[0]),$entry[1].GetAwaiter().GetResult(),$utf8)}}catch{}
  }
  if($null -ne $memoryRows){$memoryRows|Export-Csv -NoTypeInformation (Join-Path $stage 'memory.csv')}
  @{error=$failure.ToString();utc=[DateTime]::UtcNow.ToString('o');elapsed_seconds=if($null -ne $replayClock){$replayClock.Elapsed.TotalSeconds}else{$null};retained_directory=$local;timing_qualification=$false}|ConvertTo-Json|Set-Content (Join-Path $stage 'failure.json')
  throw $failure
 } finally {
  if($null -ne $process){try {if(-not $process.HasExited){$process.Kill();$process.WaitForExit()}}finally{$process.Dispose()}}
  if($complete -and (Get-Content -LiteralPath (Join-Path $local 'owned-by-validation.txt')) -eq $Run){
   Remove-Item -LiteralPath $local -Recurse -Force
  }else{Write-Output "Retained incomplete owned replay directory: $local"}
 }
}
