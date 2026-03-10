@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ═══════════════════════════════════════════════════════════════════════
::  JARVIS V20 - Ultimate Auto-Updating Launcher (Windows)
:: ═══════════════════════════════════════════════════════════════════════

:: Nastavení cest
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "PROJECT_DIR=%CD%"
set "OLLAMA_URL=http://localhost:11434"
set "GIT_REMOTE_URL=https://github.com/Julek77cz/Jarvis-v20.git"

:: 1. Donutit Windows CMD podporovat ANSI barvy (Kritický fix)
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

:: 2. Spolehlivé získání ESC znaku přes PowerShell
for /f %%A in ('powershell -NoProfile -Command "[char]27"') do set "ESC=%%A"

set "C_RESET=%ESC%[0m"
set "C_RED=%ESC%[91m"
set "C_GREEN=%ESC%[92m"
set "C_YELLOW=%ESC%[93m"
set "C_BLUE=%ESC%[94m"
set "C_MAGENTA=%ESC%[95m"
set "C_CYAN=%ESC%[96m"

cls
echo.
echo %C_CYAN% ╔═══════════════════════════════════════════════════════════╗%C_RESET%
echo %C_CYAN% ║                                                           ║%C_RESET%
echo %C_CYAN% ║         🤖 JARVIS V20 - STATE-OF-THE-ART AI AGENT         ║%C_RESET%
echo %C_CYAN% ║                                                           ║%C_RESET%
echo %C_CYAN% ╚═══════════════════════════════════════════════════════════╝%C_RESET%
echo.

:: 1. Auto-update z GitHubu
echo %C_BLUE%[1/5] Kontroluji aktualizace z GitHubu...%C_RESET%
git --version >nul 2>&1
if errorlevel 1 (
    echo %C_YELLOW%  [WARN] Git neni nainstalovan. Automaticke aktualizace nebudou fungovat.%C_RESET%
    echo %C_YELLOW%  [HINT] Pro auto-updaty si stahni Git z: https://git-scm.com/downloads%C_RESET%
) else (
    if not exist "%PROJECT_DIR%\.git" (
        echo %C_YELLOW%  [INFO] Projekt byl stazen jako ZIP. Inicializuji Git pro auto-updaty...%C_RESET%
        git init -b main >nul 2>&1
        git remote add origin %GIT_REMOTE_URL% >nul 2>&1
        git fetch origin >nul 2>&1
        git branch --set-upstream-to=origin/main main >nul 2>&1
        git pull origin main --allow-unrelated-histories >nul 2>&1
        echo %C_GREEN%  [OK] Git propojen! Od ted se bude JARVIS aktualizovat sam.%C_RESET%
    ) else (
        git remote set-url origin %GIT_REMOTE_URL% >nul 2>&1
        git pull origin main >nul 2>&1
        if errorlevel 1 (
            echo %C_YELLOW%  [WARN] Nepodarilo se stahnout aktualizace. Pouzivam lokalni verzi.%C_RESET%
        ) else (
            echo %C_GREEN%  [OK] JARVIS je aktualni.%C_RESET%
        )
    )
)
echo.

:: 2. Kontrola Pythonu
echo %C_BLUE%[2/5] Kontrola Pythonu...%C_RESET%
python --version >nul 2>&1
if errorlevel 1 (
    echo %C_RED%  [ERROR] Python neni nainstalovany nebo neni v PATH!%C_RESET%
    pause
    exit /b 1
)
echo %C_GREEN%  [OK] Python bezi v poradku.%C_RESET%
echo.

:: 3. Virtuální prostředí a závislosti
echo %C_BLUE%[3/5] Aktivace virtualniho prostredi a kontrola balicku...%C_RESET%
if exist "%PROJECT_DIR%\.venv\Scripts\activate.bat" (
    call "%PROJECT_DIR%\.venv\Scripts\activate.bat"
    python -m pip install -r requirements.txt -q
    echo %C_GREEN%  [OK] Prostredi a zavislosti jsou pripraveny.%C_RESET%
) else (
    echo %C_RED%  [ERROR] Virtualni prostredi nenalezeno! Zkus nejdriv spustit setup.bat.%C_RESET%
    pause
    exit /b 1
)
echo.

:: 4. Kontrola Ollamy
echo %C_BLUE%[4/5] Kontrola sluzby Ollama...%C_RESET%
curl -s %OLLAMA_URL%/api/tags >nul 2>&1
if errorlevel 1 (
    echo %C_YELLOW%  [WARN] Ollama nebezi. Startuji na pozadi...%C_RESET%
    start "" ollama serve
    echo %C_BLUE%  [*] Cekam na nastartovani Ollamy...%C_RESET%
    timeout /t 5 /nobreak >nul
    curl -s %OLLAMA_URL%/api/tags >nul 2>&1
    if errorlevel 1 (
        echo %C_RED%  [ERROR] Ollamu se nepodarilo spustit! Zkontroluj, zda je nainstalovana.%C_RESET%
        pause
        exit /b 1
    ) else (
        echo %C_GREEN%  [OK] Ollama uspesne nastartovana.%C_RESET%
    )
) else (
    echo %C_GREEN%  [OK] Ollama je pripravena.%C_RESET%
)
echo.

:: 5. Start JARVIS
echo %C_MAGENTA%============================================================%C_RESET%
echo %C_MAGENTA%  Startuji Mozek (V20)...%C_RESET%
echo %C_MAGENTA%============================================================%C_RESET%
echo.

python main.py %*
set EXIT_CODE=%errorlevel%

:: Konec a vyhodnoceni chyb
echo.
if %EXIT_CODE% equ 0 (
    echo %C_GREEN%============================================================%C_RESET%
    echo %C_GREEN%  JARVIS byl uspesne ukoncen.%C_RESET%
    echo %C_GREEN%============================================================%C_RESET%
) else (
    echo %C_RED%============================================================%C_RESET%
    echo %C_RED%  JARVIS spadl s chybovym kodem: %EXIT_CODE%%C_RESET%
    echo %C_RED%============================================================%C_RESET%
    echo %C_YELLOW%  [HINT] Zapni debug mod pro vice info: python main.py --debug%C_RESET%
    pause
)

exit /b %EXIT_CODE%
