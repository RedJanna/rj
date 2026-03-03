$utf8Bootstrap = Join-Path $PSScriptRoot "tools\Enable-Utf8Console.ps1"
if (Test-Path $utf8Bootstrap) {
    . $utf8Bootstrap
}

$baseUrl = $env:PUBLIC_BASE_URL
if ([string]::IsNullOrWhiteSpace($baseUrl)) {
    $baseUrl = "https://api.nexlumeai.com"
}
$baseUrl = $baseUrl.TrimEnd("/")
if ($baseUrl.EndsWith("/admin")) {
    $healthUrl = "$baseUrl/health"
}
else {
    $healthUrl = "$baseUrl/admin/health"
}

try {
    $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
    if ($response.status -ne "ok") {
        throw "Backend unhealthy"
    }
}
catch {
    Write-Output "Health check failed. Restarting services..."

    Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue
    Start-Process "cloudflared" "tunnel run nexlume-api"

    Stop-Process -Name python -Force -ErrorAction SilentlyContinue
    Start-Process "cmd.exe" "/k cd C:\KassandraOpenAI && python kassandra_openai_bot.py"
}
