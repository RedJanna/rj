@echo off
setlocal EnableExtensions
title Kassandra Backend

rem --- UTF-8 + anlik log (emoji/crash + buffer fix) ---
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "PYTHONNOUSERSITE=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

set "ROOT=%~dp0"
set "APP=%ROOT%kassandra_openai_bot.py"
set "VENV_PY=%ROOT%venv\Scripts\python.exe"
set "ELEKTRA_HOTEL_ID_DEFAULT=21966"
set "ELEKTRA_WALKIN_AGENCY_ID_DEFAULT=247664"
set "ELEKTRA_GET_RESERVATION_PATHS_DEFAULT=/hotel/{hotel_id}/reservation/get,/hotel/{hotel_id}/reservation,/hotel/{hotel_id}/getReservation,/hotel/{hotel_id}/reservation/detail,/hotel/{hotel_id}/reservations/get"
set "ELEKTRA_UPDATE_RESERVATION_PATHS_DEFAULT=/hotel/{hotel_id}/updateReservation,/hotel/{hotel_id}/reservation/update"

cd /d "%ROOT%"

echo ================================
echo BACKEND START
echo Root: %ROOT%
echo ================================

if not exist "%APP%" (
  echo HATA: %APP% bulunamadi.
  pause
  exit /b 1
)

if not exist "%VENV_PY%" (
  echo HATA: venv python bulunamadi: %VENV_PY%
  pause
  exit /b 1
)

rem --- PyMuPDF (fitz) kontrolu ---
"%VENV_PY%" -c "import fitz" >nul 2>&1
if errorlevel 1 (
  echo PyMuPDF yok, kuruluyor...
  "%VENV_PY%" -m pip install --upgrade pip
  "%VENV_PY%" -m pip install pymupdf
)

if not defined ELEKTRA_HOTEL_ID set "ELEKTRA_HOTEL_ID=%ELEKTRA_HOTEL_ID_DEFAULT%"
if not defined ELEKTRA_WALKIN_AGENCY_ID set "ELEKTRA_WALKIN_AGENCY_ID=%ELEKTRA_WALKIN_AGENCY_ID_DEFAULT%"
if not defined ELEKTRA_GET_RESERVATION_PATHS set "ELEKTRA_GET_RESERVATION_PATHS=%ELEKTRA_GET_RESERVATION_PATHS_DEFAULT%"
if not defined ELEKTRA_UPDATE_RESERVATION_PATHS set "ELEKTRA_UPDATE_RESERVATION_PATHS=%ELEKTRA_UPDATE_RESERVATION_PATHS_DEFAULT%"
echo ELEKTRA_HOTEL_ID=%ELEKTRA_HOTEL_ID%
echo ELEKTRA_WALKIN_AGENCY_ID=%ELEKTRA_WALKIN_AGENCY_ID%
echo ELEKTRA_GET_RESERVATION_PATHS=%ELEKTRA_GET_RESERVATION_PATHS%
echo ELEKTRA_UPDATE_RESERVATION_PATHS=%ELEKTRA_UPDATE_RESERVATION_PATHS%
if defined ELEKTRA_X_CAPTCHA (
  echo ELEKTRA_X_CAPTCHA=SET
) else (
  echo ELEKTRA_X_CAPTCHA=NOT_SET
)

echo.
echo Calisiyor: "%VENV_PY%" -X utf8 "%APP%"
echo (Durdurmak icin CTRL+C)
echo.

"%VENV_PY%" -X utf8 "%APP%"

echo.
echo Backend kapandi / crash oldu.
pause
