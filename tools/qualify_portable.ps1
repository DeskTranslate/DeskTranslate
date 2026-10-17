param([Parameter(Mandatory=$true)][string]$ModelDataDirectory, [switch]$Signed)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$version = (& python -c 'from desktranslate import __version__; print(__version__)').Trim()
if ($LASTEXITCODE) { throw 'Canonical version lookup failed' }
$archive = Join-Path $workspace "dist/DeskTranslate-$version-Portable-x64.zip"
if (-not (Test-Path -LiteralPath $archive)) { throw 'Portable archive is missing' }
$root = Join-Path $env:RUNNER_TEMP ('DeskTranslate portable 翻訳 ' + [Guid]::NewGuid().ToString('N'))
$work = Join-Path $root '空の 作業'
New-Item -ItemType Directory -Path $work -Force | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $root
$appRoot = Join-Path $root 'DeskTranslate'
$executable = Join-Path $appRoot 'DeskTranslate.exe'
$data = Join-Path $appRoot 'DeskTranslateData'
if (-not (Test-Path -LiteralPath (Join-Path $appRoot 'portable-mode'))) { throw 'Portable marker missing' }
$oldData = $env:DESKTRANSLATE_DATA_DIR
$oldPath = $env:PATH
$oldPythonPath = $env:PYTHONPATH
$installedData = Join-Path $env:LOCALAPPDATA 'DeskTranslate'
if (Test-Path -LiteralPath $installedData) { throw 'Use a clean disposable Windows account for portable isolation' }
$process = $null
try {
    # Verified assets are acquired separately. This tests activation/runtime, not
    # a fictitious offline download or a claim that models ship inside the ZIP.
    $env:DESKTRANSLATE_DATA_DIR = $data
    & python -c 'from pathlib import Path; import shutil,sys; from desktranslate.ocr import ModelManager; source=ModelManager(Path(sys.argv[1])); target=ModelManager(); assert source.installed("ja",verify=True); target.directory.mkdir(parents=True,exist_ok=True); [shutil.copyfile(source.path(name),target.path(name)) for name in source.required("ja")]; assert target.installed("ja",verify=True)' $ModelDataDirectory
    if ($LASTEXITCODE) { throw 'Verified model preparation failed' }
    Remove-Item Env:DESKTRANSLATE_DATA_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    $env:PATH = (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot
    $reportPath = Join-Path $workspace '.audit/portable-runtime.json'
    $fixture = Join-Path $workspace 'tests/fixtures/ja-game.png'
    $process = Start-Process -FilePath $executable -ArgumentList @('--verify-runtime',('"'+$reportPath+'"'),'--ocr-fixture',('"'+$fixture+'"')) -WorkingDirectory $work -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(120000)) { $process.Kill(); throw 'Portable probe timed out' }
    if ($process.ExitCode) { throw "Portable probe failed: $($process.ExitCode)" }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    foreach ($field in @('qt','assets','ocr_exact','http_provider_roundtrip','credential_roundtrip','credential_cleanup')) {
        if ($report.$field -ne $true) { throw "Portable runtime failed: $field" }
    }
    if (Test-Path -LiteralPath $installedData) { throw 'Portable runtime wrote installed-user data' }
    if (-not (Test-Path -LiteralPath $data)) { throw 'Portable data directory missing' }
    if ((Get-Item -LiteralPath $executable).VersionInfo.ProductVersion -ne $version) { throw 'Portable PE version mismatch' }
    $signature = (Get-AuthenticodeSignature -LiteralPath $executable).Status.ToString()
    if ($Signed -and $signature -ne 'Valid') { throw 'Portable signature verification failed' }
    if (-not $Signed -and $signature -ne 'NotSigned') { throw 'Unexpected portable signature status' }
    [ordered]@{
        version=$version; passed=$true; archive_sha256=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
        unicode_extraction_path=$true; empty_unicode_working_directory=$true; system_only_path=$true; pythonpath_removed=$true
        portable_data_isolation=$true; installed_appdata_absent=$true; runtime=$report; signature=$signature
        model_setup='Separately downloaded SHA-256-verified Japanese pack, explicitly copied to portable storage before runtime'
        scope='Hosted disposable Windows; frozen runtime with authored fixture and loopback provider. No consumer hardware or real desktop capture claim.'
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $workspace 'docs/portable-qualification.json') -Encoding utf8
} finally {
    $env:DESKTRANSLATE_DATA_DIR = $oldData
    $env:PATH = $oldPath
    $env:PYTHONPATH = $oldPythonPath
    if ($process) { $process.Dispose() }
}
