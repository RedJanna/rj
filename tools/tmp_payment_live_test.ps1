$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) {
    . $utf8Bootstrap
}

$payload = @{ phone='905399977701'; message='Odeme yaptim, dekontu da gonderdim.'; message_id=('live-payment-' + [guid]::NewGuid().ToString()) } | ConvertTo-Json -Compress
try {
  $r = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/chat' -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 120
  $r | ConvertTo-Json -Compress
} catch {
  Write-Output $_.Exception.Message
  exit 1
}
