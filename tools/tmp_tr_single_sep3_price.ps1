$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) {
    . $utf8Bootstrap
}

$phone='905399977746'
$payload=@{ phone=$phone; message='3 eylül ile 4  eylül tarihleri arasında 3 yetişkin fiyatı nedir'; message_id=('single-sep-'+[guid]::NewGuid().ToString()) } | ConvertTo-Json -Compress
$r=Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/chat' -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 120
$r | ConvertTo-Json -Compress
