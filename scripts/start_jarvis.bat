@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "PROJECT_DIR=%CD%"
set "OLLAMA_URL=http://localhost:11434"
set "GIT_REMOTE_URL=https://github.com/Julek77cz/Jarvis-v20.git"

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
call :echo_color "%CYAN%" "[JARVIS]"
call :echo_color "%MAGENTA%" "╔══════════════════════════════════════════════════════════════════════╗"
call :echo_color "%MAGENTA%" "║  JARVIS V20 - Smart start for your AI assistant                    ║"
call :echo_color "%MAGENTA%" "╚══════════════════════════════════════════════════════════════════════╝"
call :echo_color "%CYAN%" "[INFO] Initializing brain | Syncing repo | Checking Ollama"
echo.
goto :eof

:main
call :print_banner

call :echo_color "%BLUE%" "[GIT] Kontroluji aktualizace z GitHubu..."
if exist "%PROJECT_DIR%\.git" (
    git remote set-url origin %GIT_REMOTE_URL% 2>nul
    git pull origin main 2>nul
    if errorlevel 1 (
        call :echo_color "%YELLOW%" "[WARN] Aktualizace se nepodarilo stahnout. Pokracuji s lokalni verzi."
    ) else (
        call :echo_color "%GREEN%" "[OK] Repo je synchronizovane."
    )
) else (
    call :echo_color "%YELLOW%" "[WARN] .git adresar nebyl nalezen. Preskakuji aktualizaci z GitHubu."
)
echo.

python --version >nul 2>&1
if errorlevel 1 (
    call :echo_color "%RED%" "[ERR] Python neni nainstalovany nebo neni v PATH."
    pause
    exit /b 1
)
call :echo_color "%GREEN%" "[OK] Python je dostupny."

if exist "%PROJECT_DIR%\.venv\Scripts\activate.bat" (
    call :echo_color "%BLUE%" "[VENV] Aktivuji virtualni prostredi..."
    call "%PROJECT_DIR%\.venv\Scripts\activate.bat"
    call :echo_color "%BLUE%" "[PIP] Kontroluji zavislosti..."
    python -m pip install -r requirements.txt -q
    if errorlevel 1 (
        call :echo_color "%YELLOW%" "[WARN] Nepodarilo se overit vsechny zavislosti. Pokracuji..."
    ) else (
        call :echo_color "%GREEN%" "[OK] Zavislosti jsou aktualni."
    )
) else (
    call :echo_color "%RED%" "[ERR] Virtualni prostredi nebylo nalezeno. Nejdriv spust scripts\setup.bat."
    pause
    exit /b 1
)
echo.

call :echo_color "%BLUE%" "[OLLAMA] Kontroluji Ollamu..."
curl -s %OLLAMA_URL%/api/tags >nul 2>&1
if errorlevel 1 (
    call :echo_color "%YELLOW%" "[WARN] Ollama nebezi. Startuji ji na pozadi..."
    start "" ollama serve
    timeout /t 5 /nobreak >nul
    curl -s %OLLAMA_URL%/api/tags >nul 2>&1
    if errorlevel 1 (
        call :echo_color "%RED%" "[ERR] Ollama stale neodpovida. Zkontroluj instalaci."
        pause
        exit /b 1
    )
)
call :echo_color "%GREEN%" "[OK] Ollama je pripravena."
echo.
call :echo_color "%CYAN%" "[RUN] Startuji Mozek JARVIS... Hodne stesti!"
call :echo_color "%CYAN%" "══════════════════════════════════════════════════════════════════════"
echo.

python main.py %*
if errorlevel 1 (
    echo.
    call :echo_color "%RED%" "[FAIL] JARVIS skoncil s chybovym kodem %errorlevel%."
    call :echo_color "%YELLOW%" "[TIP] Mrkni na logy a zkus pripadne znovu scripts\setup.bat."
    pause
    exit /b 1
)

echo.
call :echo_color "%GREEN%" "[DONE] JARVIS byl ukoncen korektne."
