@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "PROJECT_DIR=%CD%"
set "OLLAMA_URL=http://localhost:11434"

for /f %%a in ('powershell -NoProfile -Command "$esc=[char]27; Write-Output $esc"') do set "ESC=%%a"
if not defined ESC set "ESC="

set "RESET=%ESC%[0m"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "BLUE=%ESC%[94m"
set "MAGENTA=%ESC%[95m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"

goto :main

:echo_color
echo(%~1%~2%RESET%
goto :eof

:print_banner
echo.
call :echo_color "%MAGENTA%" "╔══════════════════════════════════════════════════════════════════════╗"
call :echo_color "%MAGENTA%" "║                      🚀 JARVIS V20 LAUNCHER                        ║"
call :echo_color "%MAGENTA%" "║                 Smart start for your AI assistant                  ║"
call :echo_color "%MAGENTA%" "╚══════════════════════════════════════════════════════════════════════╝"
call :echo_color "%CYAN%" "         🤖 Initializing brain • 🔄 Syncing repo • 🛰️ Checking Ollama"
echo.
goto :eof

:main
call :print_banner

call :echo_color "%BLUE%" "[🔄] Kontroluji aktualizace z GitHubu..."
git pull
if errorlevel 1 (
    call :echo_color "%YELLOW%" "[⚠] Aktualizace se nepodarilo stahnout. Pokracuji s lokalni verzi."
) else (
    call :echo_color "%GREEN%" "[✓] Repo je synchronizovane."
)
echo.

python --version >nul 2>&1
if errorlevel 1 (
    call :echo_color "%RED%" "[✗] Python neni nainstalovany nebo neni v PATH."
    pause
    exit /b 1
)
call :echo_color "%GREEN%" "[✓] Python je dostupny."

if exist "%PROJECT_DIR%\.venv\Scripts\activate.bat" (
    call :echo_color "%BLUE%" "[🧪] Aktivuji virtualni prostredi..."
    call "%PROJECT_DIR%\.venv\Scripts\activate.bat"
    call :echo_color "%BLUE%" "[📦] Kontroluji zavislosti..."
    python -m pip install -r requirements.txt -q
    if errorlevel 1 (
        call :echo_color "%YELLOW%" "[⚠] Nepodarilo se overit vsechny zavislosti. Pokracuji..."
    ) else (
        call :echo_color "%GREEN%" "[✓] Zavislosti jsou aktualni."
    )
) else (
    call :echo_color "%RED%" "[✗] Virtualni prostredi nebylo nalezeno. Nejdriv spust scripts\setup.bat."
    pause
    exit /b 1
)
echo.

call :echo_color "%BLUE%" "[🛰️] Kontroluji Ollamu..."
curl -s %OLLAMA_URL%/api/tags >nul 2>&1
if errorlevel 1 (
    call :echo_color "%YELLOW%" "[⚠] Ollama nebezi. Startuji ji na pozadi..."
    start "" ollama serve
    timeout /t 5 /nobreak >nul
    curl -s %OLLAMA_URL%/api/tags >nul 2>&1
    if errorlevel 1 (
        call :echo_color "%RED%" "[✗] Ollama stale neodpovida. Zkontroluj instalaci."
        pause
        exit /b 1
    )
)
call :echo_color "%GREEN%" "[✓] Ollama je pripravena."
echo.
call :echo_color "%CYAN%" "[🚀] Startuji Mozek JARVIS... Hodne stesti!"
call :echo_color "%CYAN%" "══════════════════════════════════════════════════════════════════════"
echo.

python main.py %*
if errorlevel 1 (
    echo.
    call :echo_color "%RED%" "[💥] JARVIS skoncil s chybovym kodem %errorlevel%."
    call :echo_color "%YELLOW%" "[💡] Mrkni na logy a zkus pripadne znovu scripts\setup.bat."
    pause
    exit /b 1
)

echo.
call :echo_color "%GREEN%" "[🎉] JARVIS byl ukoncen korektne."
