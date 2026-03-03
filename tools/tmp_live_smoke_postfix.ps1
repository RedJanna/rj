$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) { . $utf8Bootstrap }

function Send-Chat([string]$phone, [string]$message) {
  $payload = @{ phone=$phone; message=$message; message_id=("smoke-"+[guid]::NewGuid().ToString()) } | ConvertTo-Json -Compress
  return Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -ContentType "application/json; charset=utf-8" -Body $payload -TimeoutSec 120
}

function Print-Case([string]$name, [array]$steps) {
  Write-Output ("=== " + $name + " ===")
  foreach ($m in $steps) {
    $r = Send-Chat -phone $m.phone -message $m.msg
    $reply = ($r.reply -replace "`r?`n"," | ")
    if ($reply.Length -gt 320) { $reply = $reply.Substring(0,320) }
    Write-Output ("status=" + $r.status + " | msg=" + $m.msg)
    Write-Output ("reply=" + $reply)
  }
}

# Case 1: TR fiyat
$case1 = @(
  @{ phone="905399977910"; msg="merhaba" },
  @{ phone="905399977910"; msg="14-18 Ağustos 2026 için 2 yetişkin havuz manzaralı oda fiyatı nedir" }
)

# Case 2: dil kilidi (PT)
$case2 = @(
  @{ phone="905399977911"; msg="Olá, quero saber o preço para 2 adultos de 14 a 18 de agosto de 2026" },
  @{ phone="905399977911"; msg="1" }
)

# Case 3: fiyat/ödeme çakışması
$case3 = @(
  @{ phone="905399977912"; msg="merhaba" },
  @{ phone="905399977912"; msg="14-18 Ağustos 2026 2 yetişkin fiyat" },
  @{ phone="905399977912"; msg="fiyat bilgisi verir misiniz?" }
)

Print-Case -name "CASE1_TR_PRICE" -steps $case1
Print-Case -name "CASE2_LANG_LOCK_PT" -steps $case2
Print-Case -name "CASE3_PRICE_VS_PAYMENT" -steps $case3
