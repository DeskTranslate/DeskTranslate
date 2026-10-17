$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtimeRoot = [IO.Path]::GetFullPath((Join-Path $workspace '.tools/python-3.12.15'))
if (-not $runtimeRoot.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar)) { throw 'Runtime must remain in the workspace' }
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$archive = Join-Path $runtimeRoot 'cpython-3.12.15.tar.gz'
$expected = '11ed9f8a6ac64fb1b5a55e40e305a6744a3f77a70863c8f8197a6e4349abc64a'
if (-not (Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest -Uri 'https://github.com/astral-sh/python-build-standalone/releases/download/20261009/cpython-3.12.15%2B20261009-x86_64-pc-windows-msvc-install_only_stripped.tar.gz' -OutFile $archive
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Pinned Python runtime hash mismatch' }
$tar = Join-Path $env:SystemRoot 'System32/tar.exe'
$members = & $tar -tf $archive
if ($LASTEXITCODE) { throw 'Could not inspect Python runtime archive' }
foreach ($member in $members) {
    if (-not $member.StartsWith('python/') -or ($member.Split('/') -contains '..') -or $member.Contains('\') -or $member.Contains(':')) { throw 'Unsafe Python runtime member' }
}
& $tar -xf $archive -C $runtimeRoot
if ($LASTEXITCODE) { throw 'Could not extract verified Python runtime' }
$python = Join-Path $runtimeRoot 'python/python.exe'
$version = (& $python -c 'import platform; print(platform.python_version())').Trim()
if ($LASTEXITCODE -or $version -ne '3.12.15') { throw 'Pinned Python runtime version mismatch' }
if ($env:GITHUB_PATH) { (Split-Path $python) | Out-File $env:GITHUB_PATH -Append -Encoding utf8 }
if ($env:GITHUB_ENV) {
    "DESKTRANSLATE_PYTHON_ARCHIVE_SHA256=$expected" | Out-File $env:GITHUB_ENV -Append -Encoding utf8
    'DESKTRANSLATE_PYTHON_DISTRIBUTION=astral-sh/python-build-standalone/20261009' | Out-File $env:GITHUB_ENV -Append -Encoding utf8
}
Write-Output "Verified CPython $version Windows x64 runtime"
