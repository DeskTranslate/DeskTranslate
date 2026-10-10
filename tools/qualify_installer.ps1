param([string]$PreviousInstaller = '', [switch]$Signed, [string]$OcrFixture = '', [string]$ModelDataDirectory = '')
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$version = (& python -c 'from desktranslate import __version__; print(__version__)').Trim()
if ($LASTEXITCODE) { throw 'Canonical version lookup failed' }
$setup = Join-Path $workspace "dist/DeskTranslate-$version-Setup-x64.exe"
$installRoot = [IO.Path]::GetFullPath((Join-Path $workspace '.audit/installer qualification/翻訳 app'))
$dataRoot = [IO.Path]::GetFullPath((Join-Path $workspace '.audit/installer qualification/設定 data'))
$workingRoot = [IO.Path]::GetFullPath((Join-Path $workspace '.audit/installer qualification/空の 作業'))
if (-not $installRoot.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar) -or
    -not $dataRoot.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar) -or
    -not $workingRoot.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar)) { throw 'Probe paths must stay in the workspace' }
$registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{BA24C20E-62C5-4C3B-80B4-19B02C0DBBDB}_is1'
if (Test-Path -LiteralPath $registry) {
    $existing = (Get-ItemProperty -LiteralPath $registry).InstallLocation
    if ($existing -and [IO.Path]::GetFullPath($existing).TrimEnd('\') -ne $installRoot.TrimEnd('\')) {
        throw 'Another DeskTranslate installation is registered. Run this probe in a clean Windows user/VM.'
    }
}
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
New-Item -ItemType Directory -Path $workingRoot -Force | Out-Null
if (Get-ChildItem -LiteralPath $workingRoot -Force) { throw 'Probe working directory must be empty' }
$env:DESKTRANSLATE_DATA_DIR = $dataRoot
if ($OcrFixture) {
    if (-not $ModelDataDirectory) { throw 'Verified source model directory is required for OCR qualification' }
    & python -c 'from pathlib import Path; import shutil,sys; from desktranslate.ocr import ModelManager; source=ModelManager(Path(sys.argv[1])); target=ModelManager(); assert source.installed("ja",verify=True); target.directory.mkdir(parents=True,exist_ok=True); [shutil.copyfile(source.path(name),target.path(name)) for name in source.required("ja")]; assert target.installed("ja",verify=True)' $ModelDataDirectory
    if ($LASTEXITCODE) { throw 'Could not prepare verified isolated recognition models' }
}
& python -c 'from desktranslate.settings import Settings,SettingsStore; SettingsStore().save(Settings(source="es", onboarding_done=True))'
if ($LASTEXITCODE) { throw 'Could not prepare isolated settings' }
$settingsFile = Join-Path $dataRoot 'settings.json'
$before = (Get-FileHash -LiteralPath $settingsFile).Hash
$results = [ordered]@{version=$version; setup_sha256=(Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant(); synthetic_data_only=$true; non_ascii_path=$true; non_ascii_data_path=$true; system_only_path=$true; empty_non_ascii_working_directory=$true; previous_version_upgrade=$false; installed_ocr_http_credentials_tested=$false}
function Run-Probe([string]$File, [string[]]$Arguments) {
    $previousPath = $env:PATH
    try {
        $env:PATH = (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot
        $process = Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $workingRoot -PassThru -WindowStyle Hidden
        if (-not $process.WaitForExit(120000)) { $process.Kill(); throw 'Installer/runtime probe timed out' }
        if ($process.ExitCode) { throw "Installer/runtime probe failed with exit code $($process.ExitCode)" }
    } finally { $env:PATH = $previousPath }
}
$options = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS',('/DIR="'+$installRoot+'"'))
try {
    if ($PreviousInstaller) {
        Run-Probe ([IO.Path]::GetFullPath($PreviousInstaller)) $options
        Run-Probe (Join-Path $installRoot 'DeskTranslate.exe') @('--smoke-test')
        $results.previous_version_upgrade = $true
    }
    Run-Probe $setup $options
    $results.install = Test-Path -LiteralPath (Join-Path $installRoot '_internal/desktranslate/assets/models.json')
    Run-Probe (Join-Path $installRoot 'DeskTranslate.exe') @('--smoke-test')
    $results.startup = $true
    if ($OcrFixture) {
        $runtimeReport = Join-Path $workspace '.audit/installed-runtime-beta2.json'
        Run-Probe (Join-Path $installRoot 'DeskTranslate.exe') @('--verify-runtime',('"'+$runtimeReport+'"'),'--ocr-fixture',('"'+[IO.Path]::GetFullPath($OcrFixture)+'"'))
        $runtime = Get-Content -LiteralPath $runtimeReport -Raw | ConvertFrom-Json
        if (-not $runtime.qt -or -not $runtime.assets -or -not $runtime.ocr_exact -or -not $runtime.http_provider_roundtrip -or -not $runtime.credential_roundtrip -or $runtime.credential_cleanup -eq $false) { throw 'Installed OCR/HTTP/credential qualification failed' }
        $results.installed_ocr_http_credentials_tested = $true
    }
    $results.settings_preserved_on_upgrade = (Get-FileHash -LiteralPath $settingsFile).Hash -eq $before
    Run-Probe $setup $options
    $results.reinstall = $true
    if ($Signed) {
        & (Join-Path $workspace 'packaging/verify-signature.ps1') -Artifact (Join-Path $installRoot 'DeskTranslate.exe') -Expected $env:DESKTRANSLATE_SIGNING_THUMBPRINT
        & (Join-Path $workspace 'packaging/verify-signature.ps1') -Artifact (Join-Path $installRoot 'unins000.exe') -Expected $env:DESKTRANSLATE_SIGNING_THUMBPRINT
        $results.installed_signatures_verified = $true
    }
} finally {
    $uninstaller = Join-Path $installRoot 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) { Run-Probe $uninstaller @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') }
}
$results.uninstall = -not (Test-Path -LiteralPath (Join-Path $installRoot 'DeskTranslate.exe'))
$results.settings_retained_on_uninstall = (Get-FileHash -LiteralPath $settingsFile).Hash -eq $before
$results.registry_removed = -not (Test-Path -LiteralPath $registry)
$results.passed = $results.install -and $results.startup -and $results.reinstall -and $results.settings_preserved_on_upgrade -and $results.uninstall -and $results.settings_retained_on_uninstall -and $results.registry_removed
[IO.File]::WriteAllText((Join-Path $workspace 'docs/installer-qualification.json'), ($results | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
$results | ConvertTo-Json
if (-not $results.passed) { throw 'Installer qualification failed' }
