param([Parameter(Mandatory=$true)][string]$Run,[Parameter(Mandatory=$true)][string]$Binary,[int]$Ticks=9000,[string]$Mode='public',
 [string]$Archive='<EV_ARCHIVE_DIR>\EV_Override_1.0.1.sit')
$ErrorActionPreference='Stop'
$out=Join-Path $PSScriptRoot $Run
if(Test-Path $out){throw 'Run already exists'}
New-Item -ItemType Directory $out | Out-Null
$exe=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot $Binary)).ProviderPath
$local=Join-Path ([IO.Path]::GetTempPath()) ('SystemlessEvSample-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $local | Out-Null
$saved=@{}
foreach($v in @(Get-ChildItem Env:|Where-Object {$_.Name -like 'SYSTEMLESS_*' -or $_.Name -like 'M68K_*' -or $_.Name -eq 'PROFILE_FIRE' -or $_.Name -in @('TEMP','TMP')})){$saved[$v.Name]=$v.Value}
try{
 $game=Join-Path $local 'EV_Override_1.0.1.sit'; Copy-Item -LiteralPath $Archive -Destination $game
 $copied=Join-Path $local ([IO.Path]::GetFileName($exe)); Copy-Item -LiteralPath $exe -Destination $copied
 $utf8=New-Object System.Text.UTF8Encoding($false)
 $lines=@(foreach($line in Get-Content (Join-Path $PSScriptRoot 'default-on-ev-public-diagnostic\frozen-input.txt')){$b=($line -split '#',2)[0].Trim(); if($b -and [int](($b -split '\s+')[0]) -lt $Ticks){$b}})
 $inputPath=Join-Path $local 'input.txt'; [IO.File]::WriteAllLines($inputPath,[string[]]$lines,$utf8)
 foreach($v in @(Get-ChildItem Env:|Where-Object {$_.Name -like 'SYSTEMLESS_*' -or $_.Name -like 'M68K_*' -or $_.Name -eq 'PROFILE_FIRE'})){Remove-Item -LiteralPath ('Env:'+$v.Name)}
 $env:TEMP=$local; $env:TMP=$local; $env:M68K_NATIVE_REGIONS=$Mode
 $childArgs='--headless --max-ticks '+$Ticks+' --headless-start-time 3871497600 --tick-input-script "'+$inputPath+'" "'+$game+'"'
 $sampler=Join-Path $PSScriptRoot 'sample-stacks.exe'
 $p=Start-Process -FilePath $sampler -ArgumentList ('"'+$copied+'" "'+$local+'" "'+(Join-Path $local 'samples.csv')+'" "'+$childArgs.Replace('"','\"')+'"') -WorkingDirectory $local -WindowStyle Hidden -PassThru -Wait -RedirectStandardError (Join-Path $local 'sampler-stderr.log') -RedirectStandardOutput (Join-Path $local 'sampler-stdout.log')
 foreach($f in @('samples.csv','child-stderr.log','sampler-stderr.log','sampler-stdout.log')){Copy-Item -LiteralPath (Join-Path $local $f) -Destination $out}
 @{binary=$Binary;exe_sha256=(Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant();ticks=$Ticks;mode=$Mode;exit=$p.ExitCode}|ConvertTo-Json|Set-Content (Join-Path $out 'run.json')
 Write-Output "$Run sampler exit $($p.ExitCode)"
} finally {
 Remove-Item Env:M68K_NATIVE_REGIONS -ErrorAction SilentlyContinue
 foreach($k in $saved.Keys){Set-Item -LiteralPath ('Env:'+$k) -Value $saved[$k]}
 Remove-Item -LiteralPath $local -Recurse -Force -ErrorAction SilentlyContinue
}
