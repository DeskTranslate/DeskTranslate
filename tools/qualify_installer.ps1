param([string]$PreviousInstaller = '', [switch]$Signed, [string]$OcrFixture = '', [string]$ModelDataDirectory = '', [switch]$AllowInstallChanges)
$ErrorActionPreference = 'Stop'
if (-not $AllowInstallChanges) {
    throw 'MANUAL INSTALLER QUALIFICATION: changes program files, shortcuts and per-user registration. Excluded from routine validation. Use -AllowInstallChanges only in a dedicated test account/VM.'
}
. (Join-Path $PSScriptRoot 'qualification_wait.ps1')
if (-not ('DeskTranslateQualification.ShellLinks' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;
namespace DeskTranslateQualification {
    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    class ShellLink {}
    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellLinkW {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int capacity, IntPtr findData, uint flags);
    }
    public static class ShellLinks {
        public static string Target(string file) {
            object link = new ShellLink();
            try {
                ((IPersistFile)link).Load(file, 0);
                var path = new StringBuilder(32768);
                ((IShellLinkW)link).GetPath(path, path.Capacity, IntPtr.Zero, 0);
                return path.ToString();
            } finally { Marshal.FinalReleaseComObject(link); }
        }
    }
}
'@
}
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
$modelHashes = @{}
Get-ChildItem -LiteralPath (Join-Path $dataRoot 'models') -File -ErrorAction SilentlyContinue | ForEach-Object { $modelHashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName).Hash }
$shortcutPaths = @((Join-Path ([Environment]::GetFolderPath('Programs')) 'DeskTranslate/DeskTranslate 2.lnk'), (Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'DeskTranslate 2.lnk'))
foreach ($shortcutPath in $shortcutPaths) {
    if ((Test-Path -LiteralPath $shortcutPath) -and [DeskTranslateQualification.ShellLinks]::Target($shortcutPath) -ne (Join-Path $installRoot 'DeskTranslate.exe')) { throw 'Refusing to replace a shortcut for a different installation' }
}
$results = [ordered]@{version=$version; setup_sha256=(Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant(); synthetic_data_only=$true; non_ascii_path=$true; non_ascii_data_path=$true; system_only_path=$true; empty_non_ascii_working_directory=$true; previous_version_upgrade=$false; installed_ocr_http_credentials_tested=$false}
function Run-Probe([string]$File, [string[]]$Arguments) {
    $previousPath = $env:PATH
    $process = $null
    try {
        $env:PATH = (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot
        $process = Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $workingRoot -PassThru -WindowStyle Hidden
        if (-not $process.WaitForExit(120000)) { $process.Kill(); throw 'Installer/runtime probe timed out' }
        if ($process.ExitCode) { throw "Installer/runtime probe failed with exit code $($process.ExitCode)" }
    } finally {
        $env:PATH = $previousPath
        if ($process) { $process.Dispose() }
    }
}
function Run-Uninstall {
    $uninstaller = Join-Path $installRoot 'unins000.exe'
    if (-not (Test-Path -LiteralPath $uninstaller)) {
        throw 'Expected owned uninstaller is missing'
    }
    Run-Probe $uninstaller @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
    # Inno's temporary clone can still be cleaning up after the original EXE
    # exits. Starting a reinstall then can race its deletion of unins000.exe.
    # Require observable completion; never delete leftovers to manufacture PASS.
    Wait-QualificationCondition -Label 'Owned uninstall cleanup' -Condition {
        -not (Test-Path -LiteralPath $uninstaller) -and
        -not (Test-Path -LiteralPath (Join-Path $installRoot 'DeskTranslate.exe')) -and
        -not (Test-Path -LiteralPath $registry) -and
        @($shortcutPaths | Where-Object { Test-Path -LiteralPath $_ }).Count -eq 0
    }
}
$options = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=desktopicon',('/DIR="'+$installRoot+'"'))
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
    $results.shortcuts = @($shortcutPaths | Where-Object { -not (Test-Path -LiteralPath $_) -or [DeskTranslateQualification.ShellLinks]::Target($_) -ne (Join-Path $installRoot 'DeskTranslate.exe') }).Count -eq 0
    $metadata = (Get-Item -LiteralPath (Join-Path $installRoot 'DeskTranslate.exe')).VersionInfo
    $results.executable_metadata = $metadata.ProductVersion -eq $version -and $metadata.ProductName -eq 'DeskTranslate'
    $uninstallMetadata = Get-ItemProperty -LiteralPath $registry
    $results.uninstall_metadata = $uninstallMetadata.DisplayVersion -eq $version -and [IO.Path]::GetFullPath($uninstallMetadata.InstallLocation).TrimEnd('\') -eq $installRoot.TrimEnd('\')
    if ($OcrFixture) {
        $runtimeReport = Join-Path $workspace '.audit/installed-runtime-candidate.json'
        Run-Probe (Join-Path $installRoot 'DeskTranslate.exe') @('--verify-runtime',('"'+$runtimeReport+'"'),'--ocr-fixture',('"'+[IO.Path]::GetFullPath($OcrFixture)+'"'))
        $runtime = Get-Content -LiteralPath $runtimeReport -Raw | ConvertFrom-Json
        foreach ($field in @('qt','assets','ocr_exact','ocr_cleanup','http_provider_roundtrip','credential_roundtrip','credential_cleanup')) {
            if ($runtime.$field -ne $true) { throw "Installed runtime qualification failed: $field" }
        }
        $results.installed_ocr_http_credentials_tested = $true
    }
    $results.settings_preserved_on_upgrade = (Get-FileHash -LiteralPath $settingsFile).Hash -eq $before
    $staleProbe = Join-Path $installRoot '_internal/obsolete-owned-runtime-probe.txt'
    [IO.File]::WriteAllText($staleProbe, 'Authored obsolete runtime file')
    Run-Probe $setup $options
    $results.reinstall = $true
    $results.obsolete_runtime_removed = -not (Test-Path -LiteralPath $staleProbe)
    if ($Signed) {
        & (Join-Path $workspace 'packaging/verify-signature.ps1') -Artifact (Join-Path $installRoot 'DeskTranslate.exe') -Expected $env:DESKTRANSLATE_SIGNING_THUMBPRINT
        & (Join-Path $workspace 'packaging/verify-signature.ps1') -Artifact (Join-Path $installRoot 'unins000.exe') -Expected $env:DESKTRANSLATE_SIGNING_THUMBPRINT
        $results.installed_signatures_verified = $true
    }
} finally {
    $uninstaller = Join-Path $installRoot 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) { Run-Uninstall }
}
$results.uninstall = -not (Test-Path -LiteralPath (Join-Path $installRoot 'DeskTranslate.exe'))
$results.settings_retained_on_uninstall = (Get-FileHash -LiteralPath $settingsFile).Hash -eq $before
$results.registry_removed = -not (Test-Path -LiteralPath $registry)
$results.shortcuts_removed = @($shortcutPaths | Where-Object { Test-Path -LiteralPath $_ }).Count -eq 0
$results.models_retained_on_uninstall = @($modelHashes.Keys | Where-Object { -not (Test-Path -LiteralPath (Join-Path $dataRoot "models/$_")) -or (Get-FileHash -LiteralPath (Join-Path $dataRoot "models/$_")).Hash -ne $modelHashes[$_] }).Count -eq 0
try {
    Run-Probe $setup $options
    Run-Probe (Join-Path $installRoot 'DeskTranslate.exe') @('--smoke-test')
    $results.reinstall_after_uninstall = (Get-FileHash -LiteralPath $settingsFile).Hash -eq $before
} finally {
    $uninstaller = Join-Path $installRoot 'unins000.exe'
    Run-Uninstall
}
$results.final_registry_removed = -not (Test-Path -LiteralPath $registry)
$results.final_shortcuts_removed = @($shortcutPaths | Where-Object { Test-Path -LiteralPath $_ }).Count -eq 0
$results.uninstall_cleanup_observed = $true
$results.passed = $results.install -and $results.startup -and $results.reinstall -and $results.obsolete_runtime_removed -and $results.settings_preserved_on_upgrade -and $results.uninstall -and $results.settings_retained_on_uninstall -and $results.registry_removed -and $results.shortcuts -and $results.shortcuts_removed -and $results.executable_metadata -and $results.uninstall_metadata -and $results.models_retained_on_uninstall -and $results.reinstall_after_uninstall -and $results.final_registry_removed -and $results.final_shortcuts_removed
[IO.File]::WriteAllText((Join-Path $workspace 'docs/installer-qualification.json'), ($results | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
$results | ConvertTo-Json
if (-not $results.passed) { throw 'Installer qualification failed' }
