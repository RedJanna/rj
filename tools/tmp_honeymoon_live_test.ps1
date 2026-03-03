$utf8Bootstrap = Join-Path $PSScriptRoot "Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) {
    . $utf8Bootstrap
}

$ErrorActionPreference = 'Stop'
$root = 'C:\KassandraOpenAI'
$phone = '905399988886'

function Save-Json([string]$path, [object]$obj) {
    $dir = Split-Path -Parent $path
    if (-not [string]::IsNullOrWhiteSpace($dir) -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    ($obj | ConvertTo-Json -Depth 30) | Set-Content -Path $path -Encoding UTF8
}

function Load-Json([string]$path, [object]$default) {
    if (Test-Path $path) {
        try {
            return (Get-Content -Path $path -Raw | ConvertFrom-Json -AsHashtable)
        }
        catch {
            return $default
        }
    }
    return $default
}

function Clean-Phone([string]$p) {
    return ($p -replace '\D', '')
}

function Reset-State([string]$p) {
    $conv = Join-Path $root 'conversations'
    New-Item -ItemType Directory -Path $conv -Force | Out-Null

    Get-ChildItem -Path $conv -File -Filter '*.json' -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue

    Save-Json (Join-Path $root 'data\price_flows.json') @{}
    Save-Json (Join-Path $root 'data\booking_flows.json') @{}
    Save-Json (Join-Path $root 'data\routing_states.json') @{}
    Save-Json (Join-Path $root 'data\followups.json') @{ pending = @{}; settings = @{ minutes = 10 }; last_cycle = @{} }
    Save-Json (Join-Path $root 'data\message_ids.json') @{}
    Save-Json (Join-Path $root 'rate_limits.json') @{ limits = @{}; blocked = @{} }
    Save-Json (Join-Path $root 'paused_conversations.json') @{ paused = @{} }
    Save-Json (Join-Path $root 'blacklist.json') @{ blacklist = @(); updated_at = (Get-Date).ToString('o') }

    # Karşılama mesajını atlamak için seed
    $now = Get-Date
    $seed = @{
        phone      = $p
        messages   = @(@{
                timestamp         = $now.ToString('o')
                date              = $now.ToString('yyyy-MM-dd')
                time              = $now.ToString('HH:mm:ss')
                user_message      = 'seed'
                bot_reply         = 'ack'
                is_price_template = $false
            })
        created_at = $now.ToString('o')
        updated_at = $now.ToString('o')
    }
    Save-Json (Join-Path $conv ((Clean-Phone $p) + '.json')) $seed
}

function Sanitize-Access([string]$p) {
    $clean = Clean-Phone $p

    $ratePath = Join-Path $root 'rate_limits.json'
    $rate = Load-Json $ratePath @{ limits = @{}; blocked = @{} }
    if (-not ($rate -is [hashtable])) { $rate = @{ limits = @{}; blocked = @{} } }
    if (-not $rate.ContainsKey('limits')) { $rate['limits'] = @{} }
    if (-not $rate.ContainsKey('blocked')) { $rate['blocked'] = @{} }
    [void]$rate['limits'].Remove($clean)
    [void]$rate['blocked'].Remove($clean)
    Save-Json $ratePath $rate

    $blPath = Join-Path $root 'blacklist.json'
    $bl = Load-Json $blPath @{ blacklist = @() }
    if (-not ($bl -is [hashtable])) { $bl = @{ blacklist = @() } }
    $items = @()
    if ($bl.ContainsKey('blacklist')) { $items = @($bl['blacklist']) }
    $new = @()
    foreach ($it in $items) {
        $c = Clean-Phone ([string]$it)
        if ($c -and $c -ne $clean) { $new += $c }
    }
    $bl['blacklist'] = $new
    $bl['updated_at'] = (Get-Date).ToString('o')
    Save-Json $blPath $bl

    $pausedPath = Join-Path $root 'paused_conversations.json'
    $paused = Load-Json $pausedPath @{ paused = @{} }
    if (-not ($paused -is [hashtable])) { $paused = @{ paused = @{} } }
    if (-not $paused.ContainsKey('paused') -or -not ($paused['paused'] -is [hashtable])) {
        $paused['paused'] = @{}
    }
    [void]$paused['paused'].Remove($clean)
    Save-Json $pausedPath $paused
}

function Send-Chat([string]$msg, [string]$step) {
    $payload = @{ phone = $phone; message = $msg; message_id = ('live-' + [guid]::NewGuid().ToString()) } | ConvertTo-Json -Compress
    $row = @{ step = $step; message = $msg; http_status = 0; status = ''; reason_code = ''; reply = '' }

    try {
        $resp = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/chat' -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 120
        $row['http_status'] = 200
        $row['status'] = [string]$resp.status
        $row['reason_code'] = [string]$resp.reason_code
        $row['reply'] = [string]$resp.reply
    }
    catch {
        $row['http_status'] = 0
        $row['status'] = 'request_error'
        $row['reply'] = [string]$_.Exception.Message
    }

    # İnsan devri kaynaklı blok/blacklist etkisini testte pasifleştir
    Sanitize-Access $phone
    return $row
}

Reset-State $phone

$scenario = @(
    'Merhaba, Agustos ayinda Kassandra Boutique Hotelde balayi icin konaklama planliyoruz, fiyat alabilir miyim?',
    '7-10 Agustos (3 gece) icin 2 yetiskin adina musaitlik var mi?',
    'Standart oda ile deniz manzarali oda icin toplam fiyatlari ayri ayri yazar misiniz?',
    'Kahvalti dahil mi? Degilse kisi basi gunluk ne kadar ekleniyor?',
    'Balayi paketi/susleme hizmetiniz var mi, varsa ucreti nedir?',
    'Odaya giriste kucuk bir surpriz (cicek + not) ayarlayabilir misiniz, fiyati ne olur?',
    'Aksam icin romantik masa veya ozel duzenleme yapiyor musunuz, ek ucret var mi?',
    'Iade edilebilir ve iadesiz fiyat seceneklerini, iptal kosullariyla birlikte paylasir misiniz?',
    'Check-in/check-out saatleriniz nedir, gec cikis mumkun mu?',
    'Benim glutensiz beslenme ihtiyacim var; kahvaltida uygun secenek sunabilir misiniz?',
    'Havalimani transferi ayarliyor musunuz, tek yon ve gidis-donus ucretleri nedir?',
    'Odeme yontemleriniz neler ve rezervasyonu kesinlestirmek icin kapora gerekiyor mu?',
    'Tamam, rezervasyonu baslatmak istiyorum; hangi bilgileri iletmem gerekiyor?',
    'Onaylandiktan sonra WhatsApptan teyit mesaji ve rezervasyon kodu gonderebilir misiniz?'
)

$rows = New-Object System.Collections.ArrayList
$i = 0
$injectedDone = $false

# Karşılama cevabını akışa dahil etmemek için pre-seed
[void](Send-Chat 'seed-message-ignore' 'PRE0')

foreach ($msg in $scenario) {
    $i++
    $sid = 'S' + $i.ToString('00')
    $row = Send-Chat $msg $sid
    [void]$rows.Add($row)

    if (-not $injectedDone -and $i -eq 3) {
        $x = Send-Chat 'Do you have a room suitable for 2 adults + 1 child (7 years old)?' 'X01'
        [void]$rows.Add($x)
        $injectedDone = $true

        $low = ($x.reply + '').ToLower()
        if ($low -match 'tarih|date|which dates|between|hangi tarihler') {
            $x2 = Send-Chat '18-22 August 2026' 'X02'
            [void]$rows.Add($x2)
        }
    }

    # Sistem bilgi isterse kullanıcı gibi tamamla
    $low2 = ($row.reply + '').ToLower()
    if ($low2 -match 'isim|name') { [void]$rows.Add((Send-Chat 'Gonen Test' 'A01')) }
    if ($low2 -match 'e-?mail|email') { [void]$rows.Add((Send-Chat 'gonen.test@example.com' 'A02')) }
    if ($low2 -match 'telefon|phone') { [void]$rows.Add((Send-Chat '+905399988886' 'A03')) }
    if ($low2 -match 'özel istek|special request') { [void]$rows.Add((Send-Chat 'Balayı süslemesi + 10 Ağustos 20:00 romantik masa istiyoruz.' 'A04')) }
}

# Kullanıcı isteğine göre rezervasyon oluşmuş gibi simüle et
[void]$rows.Add((Send-Chat 'Bilgileri paylaştım, test amaçlı otel ve romantik masa rezervasyonu oluşturulmuş varsayabilirsiniz.' 'SIM01'))

$reportPath = Join-Path $root 'tools\tmp_honeymoon_live_report.json'
Save-Json $reportPath @{ phone = $phone; generated_at = (Get-Date).ToString('o'); rows = @($rows) }

Write-Output '[SCENARIO_RESULT]'
foreach ($r in $rows) {
    $line = (($r.reply + '') -replace "`r?`n", ' | ')
    if ($line.Length -gt 420) { $line = $line.Substring(0, 420) + '...' }
    Write-Output ($r.step + ' | http=' + $r.http_status + ' | status=' + $r.status + ' | reason=' + $r.reason_code)
    Write-Output ('U: ' + $r.message)
    Write-Output ('B: ' + $line)
    Write-Output ''
}
Write-Output ('[REPORT] ' + $reportPath)
