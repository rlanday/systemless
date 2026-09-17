param([Parameter(Mandatory=$true)][string]$CaptureRoot, [switch]$SamplesOnly)
$proofRoot=(Resolve-Path $CaptureRoot).Path
$ErrorActionPreference='Stop'
$package=Join-Path (Split-Path $proofRoot) 'geneva-font-comparison\experiments\geneva9-fonts'
$cases=@(
 @('round7-sharp','Coppet-Round7-Sharp.ttf'),
 @('round7-entry','Coppet-Round7-Entry.ttf'),
 @('round7-combined','Coppet-Round7-Combined.ttf')
)
Remove-Item Env:SYSTEMLESS_ORIGINAL_FONTS_DIR -ErrorAction SilentlyContinue
Remove-Item Env:SYSTEMLESS_TRACE_DIALOG_TEXT -ErrorAction SilentlyContinue
foreach($case in $cases){
 $font=Join-Path $package ('generated\'+$case[1])
 $out=Join-Path $proofRoot ('review\'+$case[0])
 New-Item -ItemType Directory -Force $out | Out-Null
 $env:SYSTEMLESS_GENEVA9_COMPARISON=$font
 $p=Start-Process -FilePath (Join-Path $proofRoot 'audit-pedantic.exe') -ArgumentList @('"'+$font+'"','"'+(Join-Path $out 'masks')+'"') -WorkingDirectory $out -Wait -PassThru -RedirectStandardOutput (Join-Path $out 'glyphs.csv') -RedirectStandardError (Join-Path $out 'audit-stderr.log')
 if($p.ExitCode -ne 0){throw "Glyph audit failed: $($p.ExitCode)"}
 $p=Start-Process -FilePath (Join-Path $proofRoot 'render-round3.exe') -ArgumentList ('"'+$out+'"') -WorkingDirectory $out -Wait -PassThru -RedirectStandardOutput (Join-Path $out 'samples-stdout.log') -RedirectStandardError (Join-Path $out 'samples-stderr.log')
 if($p.ExitCode -ne 0){throw "Samples failed: $($p.ExitCode)"}
 if(-not $SamplesOnly){
  $p=Start-Process -FilePath (Join-Path $proofRoot 'render-round3.exe') -ArgumentList ('--city "'+(Join-Path (Split-Path $proofRoot) 'sc2k-expanded-test.kpak')+'" "'+$out+'"') -WorkingDirectory $out -Wait -PassThru -RedirectStandardOutput (Join-Path $out 'city-stdout.log') -RedirectStandardError (Join-Path $out 'city-stderr.log')
  if($p.ExitCode -ne 0){throw "City replay failed: $($p.ExitCode)"}
 }
 Write-Output "Completed $($case[0])."
}
