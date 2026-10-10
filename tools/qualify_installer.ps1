param([string]$PreviousInstaller = '', [switch]$Signed)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$version = (& python -c 'from desktranslate import __version__; print(__version__)').Trim()
if ($LASTEXITCODE) { throw 'Canonical version lookup failed' }
$setup = Join-Path $workspace "dist/DeskTranslate-$version-Setup-x64.exe"
$installRoot = [IO.Path]::GetFullPath((Join-Path $workspace '.audit/installer qualification/翻訳 app'))
$dataRoot = [IO.Path]::GetFullPath((Join-Path $workspace '.audit/installer qualification/settings'))
if (-not $installRoot.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar) -or
    -not $dataRoot.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar)) { throw 'Probe paths must stay in the workspace' }
$registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{BA24C20E-62C5-4C3B-80B4-19B02C0DBBDB}_is1'
if (Test-Path -LiteralPath $registry) {
    $existing = (Get-ItemProperty -LiteralPath $registry).InstallLocation
    if ($existing -and [IO.Path]::GetFullPath($existing).TrimEnd('\') -ne $installRoot.TrimEnd('\')) {
        throw 'Another DeskTranslate installation is registered. Run this probe in a clean Windows user/VM.'
    }
}
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
$env:DESKTRANSLATE_DATA_DIR = $dataRoot
& python -c 'from desktranslate.settings import Settings,SettingsStore; SettingsStore().save(Settings(source="es", onboarding_done=True))'
if ($LASTEXITCODE) { throw 'Could not prepare isolated settings' }
$settingsFile = Join-Path $dataRoot 'settings.json'
$before = (Get-FileHash -LiteralPath $settingsFile).Hash
$results = [ordered]@{version=$version; synthetic_data_only=$true; non_ascii_path=$true; previous_version_upgrade=$false}
function Run-Probe([string]$File, [string[]]$Arguments) {
    $process = Start-Process -FilePath $File -ArgumentList $Arguments -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(120000)) { $process.Kill(); throw 'Installer/runtime probe timed out' }
    if ($process.ExitCode) { throw "Installer/runtime probe failed with exit code $($process.ExitCode)" }
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
$results | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workspace 'docs/installer-qualification.json') -Encoding utf8
$results | ConvertTo-Json
if (-not $results.passed) { throw 'Installer qualification failed' }
