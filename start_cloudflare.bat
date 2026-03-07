@echo off
setlocal EnableExtensions
title Cloudflare Tunnel

set "ROOT=%~dp0"
set "TUNNEL_NAME=%CF_TUNNEL_NAME%"
if "%TUNNEL_NAME%"=="" set "TUNNEL_NAME=nexlume-api"
set "CF_EXE=%ProgramFiles(x86)%\cloudflared\cloudflared.exe"

cd /d "%ROOT%"

echo ================================
echo CLOUDFLARE TUNNEL START
echo Tunnel: %TUNNEL_NAME%
echo ================================

if exist "%CF_EXE%" (
  echo cloudflared: "%CF_EXE%"
  echo.
  echo Tunnel basliyor... (Durdurmak icin CTRL+C)
  "%CF_EXE%" tunnel run %TUNNEL_NAME%
  echo.
  echo Tunnel kapandi / crash oldu.
  pause
  exit /b 0
)

echo HATA: cloudflared.exe bulunamadi:
echo   %CF_EXE%
echo Cozum:
echo   - cloudflared'i bu konuma kur veya PATH'e ekle
echo.
pause
