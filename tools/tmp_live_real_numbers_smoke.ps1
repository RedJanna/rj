$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) { . $utf8Bootstrap }

function Send-Chat([string]$phone, [string]$message) {
  $payload = @{ phone=$phone; message=$message; message_id=("real-smoke-"+[guid]::NewGuid().ToString()) } | ConvertTo-Json -Compress
  return Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -ContentType "application/json; charset=utf-8" -Body $payload -TimeoutSec 120
}

function Run-Scenario([string]$phone, [string]$name) {
  Write-Output ("=== " + $name + " | " + $phone + " ===")
  $msgs = @(
    "merhaba",
    "14-18 Ağustos 2026 için 2 yetişkin havuz manzaralı oda fiyatı nedir",
    "fiyat bilgisi verir misiniz?"
  )
  foreach ($m in $msgs) {
    $r = Send-Chat -phone $phone -message $m
    $reply = ($r.reply -replace "`r?`n"," | ")
    if ($reply.Length -gt 360) { $reply = $reply.Substring(0,360) }
    Write-Output ("status=" + $r.status + " | msg=" + $m)
    Write-Output ("reply=" + $reply)
  }
}

Run-Scenario -phone "905332503277" -name "CASE_A"
Run-Scenario -phone "905304498453" -name "CASE_B"
