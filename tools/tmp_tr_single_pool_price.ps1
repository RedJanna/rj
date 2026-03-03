$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) {
    . $utf8Bootstrap
}

$phone='905399977747'
$payload=@{ phone=$phone; message='14-18 Ağustos, 2 yetişkin, havuz manzaralı oda fiyatı nedir'; message_id=('single-pool-'+[guid]::NewGuid().ToString()) } | ConvertTo-Json -Compress
$r=Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/chat' -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 120
$r | ConvertTo-Json -Compress
