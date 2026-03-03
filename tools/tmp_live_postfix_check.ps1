$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) {
    . $utf8Bootstrap
}

$phone='905399977745'
$msgs=@(
  '14-18 Ağustos, 2 yetişkin, havuz manzaralı oda fiyatı nedir',
  '14 ağustos ile 18 ağustos tarihler arasında 2 yetişkin fiyatı nedir',
  '3 eylül ile 4  eylül tarihleri arasında 3 yetişkin fiyatı nedir'
)
$i=0
foreach($m in $msgs){
  $i=$i+1
  $payload=@{ phone=$phone; message=$m; message_id=('postfix-'+$i+'-'+[guid]::NewGuid().ToString()) } | ConvertTo-Json -Compress
  $r=Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/chat' -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 120
  ([PSCustomObject]@{step=$i; status=$r.status; is_price_template=$r.is_price_template; reply=$r.reply}) | ConvertTo-Json -Compress
}
