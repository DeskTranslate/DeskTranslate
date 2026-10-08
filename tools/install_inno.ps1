$ErrorActionPreference = 'Stop'
$compilerRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.tools/inno'))
$installerFile = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.tools/innosetup-6.7.3.exe'))
New-Item -ItemType Directory -Path (Split-Path $installerFile) -Force | Out-Null
Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $installerFile
if ((Get-FileHash -LiteralPath $installerFile -Algorithm SHA256).Hash -ne '9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732') { throw 'Inno installer hash mismatch' }
$signature = Get-AuthenticodeSignature -LiteralPath $installerFile
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Pyrsys B.V.') { throw 'Inno installer signature mismatch' }
$process = Start-Process -FilePath $installerFile -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', ('/DIR="'+$compilerRoot+'"'), '/NOICONS') -PassThru -WindowStyle Hidden
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw "Compiler installation failed: $($process.ExitCode)" }
