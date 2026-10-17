param(
    [Parameter(Mandatory=$true)][string]$Artifact,
    [Parameter(Mandatory=$true)][string]$Expected
)
$ErrorActionPreference = 'Stop'
$signature = Get-AuthenticodeSignature -LiteralPath $Artifact
if ($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate -or
    $signature.SignerCertificate.Thumbprint -ne $Expected -or
    $signature.SignerCertificate.Subject -eq $signature.SignerCertificate.Issuer) {
    throw 'Publisher signature, trust chain or timestamp verification failed'
}
