$healthUrl = "http://127.0.0.1:8000/admin/health"

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
