$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) {
    . $utf8Bootstrap
}

$phone = "905399977799"
$msgs = @(
  "merhaba",
  "14-18 Ağustos, 2 yetişkin, havuz manzaralı oda fiyatı nedir",
  "fiyat bilgisi verir misiniz?"
)

$i = 0
foreach ($m in $msgs) {
  $i = $i + 1
  $payload = @{ phone = $phone; message = $m; message_id = "post-fix-" + [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
  $r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -ContentType "application/json; charset=utf-8" -Body $payload -TimeoutSec 120
  Write-Output ("$i|STATUS=" + $r.status)
  $reply = ($r.reply -replace "`r?`n", " | ")
  if ($reply.Length -gt 500) { $reply = $reply.Substring(0,500) }
  Write-Output ("$i|REPLY=" + $reply)
}
