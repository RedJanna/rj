@echo off
setlocal EnableExtensions
title Kassandra Backend

:RESTART
rem --- UTF-8 + anlik log (emoji/crash + buffer fix) ---
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "PYTHONNOUSERSITE=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

set "ROOT=%~dp0"
set "APP=%ROOT%kassandra_openai_bot.py"
set "PREFLIGHT=%ROOT%tools\preflight_check.py"
set "VENV_PY=%ROOT%venv\Scripts\python.exe"
set "UVICORN_MODULE=app.main:app"
set "UVICORN_RELOAD_FLAGS="
set "BACKEND_RUNNER_DEFAULT=uvicorn"
set "BACKEND_HOST_DEFAULT=0.0.0.0"
set "BACKEND_PORT_DEFAULT=8000"
set "BACKEND_RELOAD_DEFAULT=0"
set "BACKEND_PREFLIGHT_DEFAULT=1"
set "BACKEND_AUTO_RESTART_DEFAULT=0"
set "BACKEND_ACCESS_LOG_DEFAULT=0"
set "BACKEND_BOOT_LOG_FILE=backend_boot.log"
set "BACKEND_BOOT_LOG_DIR=logs"
set "BACKEND_BOOT_BACKUP_DIR=logs\boot_backups"
set "BACKEND_BOOT_FALLBACK_LOG_FILE=logs\backend_boot_fallback.log"
set "BACKEND_FILE_LOG_DEFAULT=1"
set "BACKEND_BOOT_LOG_MAX_MB_DEFAULT=25"
set "BACKEND_BOOT_LOG_KEEP_DEFAULT=10"
set "BACKEND_BOOT_BACKUP_KEEP_DEFAULT=200"
set "ELEKTRA_HOTEL_ID_DEFAULT=21966"
set "ELEKTRA_WALKIN_AGENCY_ID_DEFAULT=247664"
set "ELEKTRA_GET_RESERVATION_PATHS_DEFAULT=/hotel/{hotel_id}/reservation/get,/hotel/{hotel_id}/reservation,/hotel/{hotel_id}/getReservation,/hotel/{hotel_id}/reservation/detail,/hotel/{hotel_id}/reservations/get"
set "ELEKTRA_UPDATE_RESERVATION_PATHS_DEFAULT=/hotel/{hotel_id}/updateReservation,/hotel/{hotel_id}/reservation/update"

cd /d "%ROOT%"

if not defined BACKEND_BOOT_LOG_MAX_MB set "BACKEND_BOOT_LOG_MAX_MB=%BACKEND_BOOT_LOG_MAX_MB_DEFAULT%"
if not defined BACKEND_BOOT_LOG_KEEP set "BACKEND_BOOT_LOG_KEEP=%BACKEND_BOOT_LOG_KEEP_DEFAULT%"
if not defined BACKEND_BOOT_BACKUP_KEEP set "BACKEND_BOOT_BACKUP_KEEP=%BACKEND_BOOT_BACKUP_KEEP_DEFAULT%"
if not defined BACKEND_FILE_LOG set "BACKEND_FILE_LOG=%BACKEND_FILE_LOG_DEFAULT%"
if not exist "%ROOT%%BACKEND_BOOT_LOG_DIR%" mkdir "%ROOT%%BACKEND_BOOT_LOG_DIR%" >nul 2>&1
if not exist "%ROOT%%BACKEND_BOOT_BACKUP_DIR%" mkdir "%ROOT%%BACKEND_BOOT_BACKUP_DIR%" >nul 2>&1
if "%BACKEND_FILE_LOG%"=="1" (
  call :rotate_boot_log_if_needed
  call :resolve_boot_log_target
) else (
  set "BACKEND_LOGGING_ENABLED=0"
  echo NOT: BACKEND_FILE_LOG=0, dosya logu kapali.
)

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
if not defined ELEKTRA_API_BASE_URL set "ELEKTRA_API_BASE_URL=https://bookingapi.elektraweb.com"
if not defined BACKEND_RUNNER set "BACKEND_RUNNER=%BACKEND_RUNNER_DEFAULT%"
set "BACKEND_RUNNER_CLEAN=%BACKEND_RUNNER:"=%"
for /f "tokens=* delims= " %%R in ("%BACKEND_RUNNER_CLEAN%") do set "BACKEND_RUNNER_CLEAN=%%R"
if not defined BACKEND_HOST set "BACKEND_HOST=%BACKEND_HOST_DEFAULT%"
if not defined BACKEND_PORT set "BACKEND_PORT=%BACKEND_PORT_DEFAULT%"
if not defined BACKEND_RELOAD set "BACKEND_RELOAD=%BACKEND_RELOAD_DEFAULT%"
if not defined BACKEND_PREFLIGHT set "BACKEND_PREFLIGHT=%BACKEND_PREFLIGHT_DEFAULT%"
if not defined BACKEND_AUTO_RESTART set "BACKEND_AUTO_RESTART=%BACKEND_AUTO_RESTART_DEFAULT%"
if not defined BACKEND_ACCESS_LOG set "BACKEND_ACCESS_LOG=%BACKEND_ACCESS_LOG_DEFAULT%"
if not defined APP_DEPLOYED_AT (
  for /f "delims=" %%T in ('"%VENV_PY%" -c "from datetime import datetime; print(datetime.now().astimezone().isoformat())" 2^>nul') do set "APP_DEPLOYED_AT=%%T"
)
if not defined APP_DEPLOYED_AT (
  echo UYARI: APP_DEPLOYED_AT otomatik uretilemedi.
)
echo ELEKTRA_HOTEL_ID=%ELEKTRA_HOTEL_ID%
echo ELEKTRA_API_BASE_URL=%ELEKTRA_API_BASE_URL%
echo ELEKTRA_WALKIN_AGENCY_ID=%ELEKTRA_WALKIN_AGENCY_ID%
echo ELEKTRA_GET_RESERVATION_PATHS=%ELEKTRA_GET_RESERVATION_PATHS%
echo ELEKTRA_UPDATE_RESERVATION_PATHS=%ELEKTRA_UPDATE_RESERVATION_PATHS%
echo BACKEND_RUNNER=%BACKEND_RUNNER%
echo BACKEND_RUNNER_CLEAN=%BACKEND_RUNNER_CLEAN%
echo BACKEND_HOST=%BACKEND_HOST%
echo BACKEND_PORT=%BACKEND_PORT%
echo BACKEND_RELOAD=%BACKEND_RELOAD%
echo BACKEND_PREFLIGHT=%BACKEND_PREFLIGHT%
echo BACKEND_AUTO_RESTART=%BACKEND_AUTO_RESTART%
echo BACKEND_ACCESS_LOG=%BACKEND_ACCESS_LOG%
echo BACKEND_FILE_LOG=%BACKEND_FILE_LOG%
echo APP_DEPLOYED_AT=%APP_DEPLOYED_AT%
if defined ELEKTRA_X_CAPTCHA (
  echo ELEKTRA_X_CAPTCHA=SET
) else (
  echo ELEKTRA_X_CAPTCHA=NOT_SET
)
if defined Elektra_Booking (
  echo Elektra_Booking=SET
) else (
  echo Elektra_Booking=NOT_SET
)

echo.
if "%BACKEND_PREFLIGHT%"=="1" (
  if not exist "%PREFLIGHT%" (
    echo HATA: preflight script bulunamadi: %PREFLIGHT%
    pause
    exit /b 1
  )
  echo Preflight calisiyor: "%VENV_PY%" "%PREFLIGHT%"
  "%VENV_PY%" "%PREFLIGHT%"
  if errorlevel 1 (
    echo.
    echo Preflight basarisiz. Backend baslatilmadi.
    pause
    exit /b 1
  )
  echo.
)

set "RUNNER_IS_UVICORN=0"
if /I "%BACKEND_RUNNER_CLEAN%"=="uvicorn" set "RUNNER_IS_UVICORN=1"
if /I not "%BACKEND_RUNNER_CLEAN:uvicorn=%"=="%BACKEND_RUNNER_CLEAN%" set "RUNNER_IS_UVICORN=1"

if "%RUNNER_IS_UVICORN%"=="1" (
  set "UVICORN_ACCESS_LOG_FLAG="
  if "%BACKEND_ACCESS_LOG%"=="0" set "UVICORN_ACCESS_LOG_FLAG=--no-access-log"
  if "%BACKEND_RELOAD%"=="1" (
    set "UVICORN_RELOAD_FLAGS=--reload-dir app"
    "%VENV_PY%" -c "import watchfiles" >nul 2>&1
    if not errorlevel 1 (
      set "UVICORN_RELOAD_FLAGS=%UVICORN_RELOAD_FLAGS% --reload-exclude .venv --reload-exclude venv"
    )
    echo Calisiyor: "%VENV_PY%" -m uvicorn %UVICORN_MODULE% --host %BACKEND_HOST% --port %BACKEND_PORT% --reload %UVICORN_RELOAD_FLAGS% %UVICORN_ACCESS_LOG_FLAG%
    echo (Durdurmak icin CTRL+C)
    echo.
    call :ensure_log_stream_ready
    if "%BACKEND_LOGGING_ENABLED%"=="1" (
      call :log_line "=================================================="
      call :log_line "[START %date% %time%] runner=uvicorn reload=1 host=%BACKEND_HOST% port=%BACKEND_PORT%"
      call :backup_boot_log start
      "%VENV_PY%" -m uvicorn %UVICORN_MODULE% --host %BACKEND_HOST% --port %BACKEND_PORT% --reload %UVICORN_RELOAD_FLAGS% %UVICORN_ACCESS_LOG_FLAG% >> "%BACKEND_LOG_TARGET%" 2>&1
    ) else (
      "%VENV_PY%" -m uvicorn %UVICORN_MODULE% --host %BACKEND_HOST% --port %BACKEND_PORT% --reload %UVICORN_RELOAD_FLAGS% %UVICORN_ACCESS_LOG_FLAG%
    )
  ) else (
    echo Calisiyor: "%VENV_PY%" -m uvicorn %UVICORN_MODULE% --host %BACKEND_HOST% --port %BACKEND_PORT% %UVICORN_ACCESS_LOG_FLAG%
    echo (Durdurmak icin CTRL+C)
    echo.
    call :ensure_log_stream_ready
    if "%BACKEND_LOGGING_ENABLED%"=="1" (
      call :log_line "=================================================="
      call :log_line "[START %date% %time%] runner=uvicorn reload=0 host=%BACKEND_HOST% port=%BACKEND_PORT%"
      call :backup_boot_log start
      "%VENV_PY%" -m uvicorn %UVICORN_MODULE% --host %BACKEND_HOST% --port %BACKEND_PORT% %UVICORN_ACCESS_LOG_FLAG% >> "%BACKEND_LOG_TARGET%" 2>&1
    ) else (
      "%VENV_PY%" -m uvicorn %UVICORN_MODULE% --host %BACKEND_HOST% --port %BACKEND_PORT% %UVICORN_ACCESS_LOG_FLAG%
    )
  )
) else (
  echo Calisiyor: "%VENV_PY%" -X utf8 "%APP%"
  echo (Durdurmak icin CTRL+C)
  echo.
  call :ensure_log_stream_ready
  if "%BACKEND_LOGGING_ENABLED%"=="1" (
    call :log_line "=================================================="
    call :log_line "[START %date% %time%] runner=python app=%APP%"
    call :backup_boot_log start
    "%VENV_PY%" -X utf8 "%APP%" >> "%BACKEND_LOG_TARGET%" 2>&1
  ) else (
    "%VENV_PY%" -X utf8 "%APP%"
  )
)

echo.
echo Backend kapandi / crash oldu.
if "%BACKEND_LOGGING_ENABLED%"=="1" (
  call :log_line "[STOP  %date% %time%] Backend kapandi veya process sonlandi."
  call :backup_boot_log stop
)
if "%BACKEND_AUTO_RESTART%"=="1" (
  echo Otomatik restart aktif. 2 saniye sonra yeniden baslatiliyor...
  timeout /t 2 >nul
  goto RESTART
)
choice /C RX /N /M "Restart icin R, cikis icin X: "
if errorlevel 2 exit /b 0
if errorlevel 1 goto RESTART

:rotate_boot_log_if_needed
set "BOOT_LOG_PATH=%ROOT%%BACKEND_BOOT_LOG_FILE%"
if not exist "%BOOT_LOG_PATH%" goto :eof

for %%I in ("%BOOT_LOG_PATH%") do set "BOOT_LOG_SIZE=%%~zI"
set /a "BOOT_LOG_MAX_BYTES=%BACKEND_BOOT_LOG_MAX_MB%*1024*1024"
if %BOOT_LOG_SIZE% LSS %BOOT_LOG_MAX_BYTES% goto :eof

for /f "delims=" %%T in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set "BOOT_LOG_TS=%%T"
set "BOOT_LOG_ARCHIVE=%ROOT%%BACKEND_BOOT_LOG_DIR%\backend_boot_%BOOT_LOG_TS%.log"
move /y "%BOOT_LOG_PATH%" "%BOOT_LOG_ARCHIVE%" >nul 2>&1
if errorlevel 1 (
  echo UYARI: backend_boot.log kilitli oldugu icin rotate atlandi.
  goto :eof
)
echo [LOG ROTATE] backend_boot.log arsave tasindi: %BOOT_LOG_ARCHIVE%

for /f "skip=%BACKEND_BOOT_LOG_KEEP% delims=" %%F in ('dir /b /a-d /o-d "%ROOT%%BACKEND_BOOT_LOG_DIR%\backend_boot_*.log" 2^>nul') do (
  del /q "%ROOT%%BACKEND_BOOT_LOG_DIR%\%%F" >nul 2>&1
)
goto :eof

:resolve_boot_log_target
set "BACKEND_LOGGING_ENABLED=1"
set "BACKEND_LOG_TARGET=%ROOT%%BACKEND_BOOT_LOG_FILE%"
call :can_write_log "%BACKEND_LOG_TARGET%"
if not errorlevel 1 goto :eof
set "BACKEND_LOG_TARGET=%ROOT%%BACKEND_BOOT_FALLBACK_LOG_FILE%"
echo UYARI: backend_boot.log kilitli; fallback log kullaniliyor: %BACKEND_LOG_TARGET%
call :can_write_log "%BACKEND_LOG_TARGET%"
if not errorlevel 1 goto :eof
echo UYARI: fallback log da kilitli. Bu calismada dosya logu devre disi.
set "BACKEND_LOGGING_ENABLED=0"
goto :eof

:backup_boot_log
set "BOOT_LOG_PATH=%ROOT%%BACKEND_BOOT_LOG_FILE%"
if not exist "%BOOT_LOG_PATH%" goto :eof
set "BACKUP_EVENT=%~1"
if "%BACKUP_EVENT%"=="" set "BACKUP_EVENT=event"
for /f "delims=" %%T in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss_fff\")"') do set "BOOT_BACKUP_TS=%%T"
set "BOOT_BACKUP_PATH=%ROOT%%BACKEND_BOOT_BACKUP_DIR%\backend_boot_%BACKUP_EVENT%_%BOOT_BACKUP_TS%.log"
copy /y "%BOOT_LOG_PATH%" "%BOOT_BACKUP_PATH%" >nul 2>&1
if errorlevel 1 (
  echo UYARI: backend_boot.log yedegi alinamadi. event=%BACKUP_EVENT%
  goto :eof
)
for /f "skip=%BACKEND_BOOT_BACKUP_KEEP% delims=" %%F in ('dir /b /a-d /o-d "%ROOT%%BACKEND_BOOT_BACKUP_DIR%\backend_boot_*.log" 2^>nul') do (
  del /q "%ROOT%%BACKEND_BOOT_BACKUP_DIR%\%%F" >nul 2>&1
)
goto :eof

:can_write_log
set "LOG_TEST_PATH=%~1"
if "%LOG_TEST_PATH%"=="" exit /b 1
powershell -NoProfile -Command "$p=$env:LOG_TEST_PATH; try { $dir=[System.IO.Path]::GetDirectoryName($p); if($dir -and -not (Test-Path $dir)){ New-Item -ItemType Directory -Path $dir -Force | Out-Null }; $fs=[System.IO.File]::Open($p,[System.IO.FileMode]::Append,[System.IO.FileAccess]::Write,[System.IO.FileShare]::ReadWrite); $fs.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:ensure_log_stream_ready
if not "%BACKEND_LOGGING_ENABLED%"=="1" goto :eof
call :can_write_log "%BACKEND_LOG_TARGET%"
if not errorlevel 1 goto :eof
echo UYARI: log dosyasi kilitli. Bu calismada dosya logu kapatildi.
set "BACKEND_LOGGING_ENABLED=0"
goto :eof

:log_line
if not "%BACKEND_LOGGING_ENABLED%"=="1" goto :eof
set "LOG_LINE=%~1"
set "LOG_APPEND_PATH=%BACKEND_LOG_TARGET%"
powershell -NoProfile -Command "$p=$env:LOG_APPEND_PATH; $line=$env:LOG_LINE; try { Add-Content -LiteralPath $p -Value $line -Encoding UTF8 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 set "BACKEND_LOGGING_ENABLED=0"
goto :eof
