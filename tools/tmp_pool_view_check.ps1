$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) {
    . $utf8Bootstrap
}

$phone='905399977889'
$msgs=@(
  '14-18 Ağustos 2026 için 2 yetişkin havuz manzaralı oda fiyatını öğrenmek istiyorum.',
  'Sadece havuz manzaralı seçenekleri ve fiyatlarını yaz lütfen.'
)
foreach($m in $msgs){
  $payload=@{ phone=$phone; message=$m; message_id=('pool-'+[guid]::NewGuid().ToString()) } | ConvertTo-Json -Compress
  $r=Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/chat' -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 90
  Write-Output ('STATUS=' + $r.status)
  $reply = ($r.reply -replace "`r?`n",' | ')
  Write-Output ('REPLY=' + $reply)
}
