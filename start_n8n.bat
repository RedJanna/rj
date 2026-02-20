@echo off
setlocal EnableExtensions
title n8n

set "ROOT=%~dp0"
set "WEBHOOK_URL=https://webhook.nexlumeai.com"

cd /d "%ROOT%"

echo ================================
echo N8N START
echo Root: %ROOT%
echo WEBHOOK_URL=%WEBHOOK_URL%
echo ================================

REM n8n komutunu bul
where n8n >nul 2>&1
if errorlevel 1 (
  echo HATA: n8n komutu PATH'te bulunamadi.
  echo Denenecek alternatif: npx n8n
  where npx >nul 2>&1
  if errorlevel 1 (
    echo HATA: npx de bulunamadi. Node.js / npm / n8n kurulumunu kontrol et.
    pause
    exit /b 1
  )
  set "WEBHOOK_URL=%WEBHOOK_URL%"
  echo.
  echo npx ile baslatiliyor... (Durdurmak icin CTRL+C)
  npx n8n
  echo.
  echo n8n kapandi / crash oldu.
  pause
  exit /b 0
)

set "WEBHOOK_URL=%WEBHOOK_URL%"
echo.
echo n8n basliyor... (Durdurmak icin CTRL+C)
n8n

echo.
echo n8n kapandi / crash oldu.
pause
