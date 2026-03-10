@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "PROJECT_DIR=%CD%"
set "OLLAMA_URL=http://localhost:11434"
set "GIT_REMOTE_URL=https://github.com/Julek77cz/Jarvis-v20.git"

:: Simple ANSI colors (NO PowerShell)
set "C_RESET=[0m"
set "C_RED=[91m"
set "C_GREEN=[92m"
set "C_YELLOW=[93m"
set "C_BLUE=[94m"
set "C_MAGENTA=[95m"
set "C_CYAN=[96m"

:: Print JARVIS ASCII banner
echo.
echo %C_CYAN%  _____                _   _               _    __ _     _
echo %C_CYAN% ^|  _ \              ^| ^| ^| ^|             ^| ^|  / /_)   ^| ^|
echo %C_CYAN% ^| ^|_) ^| __ _  ___  ^| ^|_^| ^|_  ___  _ __^| ^|/ /_  ___^| ^|_
echo %C_CYAN% ^|  _ _/ / _` ^|/ _ \^| __^| __^| ^|/ _ \^| '__^|   _/ / \^|/ _ \ __^|
echo %C_CYAN% ^| ^|_) ^| (_^| ^| (_) ^| ^|_^| ^|_^| ^|_^| ^| ^| ^|  ^| ^|\  /  ^|  ^|^|_^| ^|
echo %C_CYAN% ^|____/ \__,_^|\___/ \__^|\__^|\___/ ^|_^|  ^|_^| \_^|   ^|_\___^|_^|
echo.
echo %C_MAGENTA%============================================================
echo %C_MAGENTA%  JARVIS V20 - State-of-the-Art AI Agent
echo %C_MAGENTA%============================================================
echo %C_RESET%

:: 1. GitHub sync
echo %C_BLUE%[1/6] Checking GitHub repository...%C_RESET%
if exist "%PROJECT_DIR%\.git" (
    git remote set-url origin %GIT_REMOTE_URL% 2>nul
    git pull origin main 2>nul
    if errorlevel 1 (
        echo %C_YELLOW%  [WARN] Git pull failed, using local version.%C_RESET%
    ) else (
        echo %C_GREEN%  [OK] Repository synchronized.%C_RESET%
    )
) else (
    echo %C_YELLOW%  [WARN] .git directory not found.%C_RESET%
)
echo.

:: 2. Python check
echo %C_BLUE%[2/6] Checking Python installation...%C_RESET%
python --version 2>nul
if errorlevel 1 (
    echo %C_RED%  [ERROR] Python is not installed or not in PATH!%C_RESET%
    pause
    exit /b 1
)
echo %C_GREEN%  [OK] Python is available.%C_RESET%
echo.

:: 3. Virtual environment
echo %C_BLUE%[3/6] Activating virtual environment...%C_RESET%
if exist "%PROJECT_DIR%\.venv\Scripts\activate.bat" (
    call "%PROJECT_DIR%\.venv\Scripts\activate.bat"
    echo %C_GREEN%  [OK] Virtual environment activated.%C_RESET%
) else (
    echo %C_RED%  [ERROR] Virtual environment not found!%C_RESET%
    pause
    exit /b 1
)
echo.

:: 4. Dependencies
echo %C_BLUE%[4/6] Installing dependencies...%C_RESET%
pip install -r requirements.txt -q 2>nul
if errorlevel 1 (
    echo %C_YELLOW%  [WARN] Some dependencies may have failed to install.%C_RESET%
) else (
    echo %C_GREEN%  [OK] Dependencies installed.%C_RESET%
)
echo.

:: 5. Ollama check
echo %C_BLUE%[5/6] Checking Ollama service...%C_RESET%
curl -s %OLLAMA_URL%/api/tags >nul 2>&1
if errorlevel 1 (
    echo %C_YELLOW%  [WARN] Ollama is not running. Starting...%C_RESET%
    start "" ollama serve
    echo %C_BLUE%  [*] Waiting 8 seconds for Ollama to start...%C_RESET%
    timeout /t 8 /nobreak >nul
    curl -s %OLLAMA_URL%/api/tags >nul 2>&1
    if errorlevel 1 (
        echo %C_RED%  [ERROR] Ollama failed to start!%C_RESET%
        echo %C_YELLOW%  [HINT] Make sure Ollama is installed: https://ollama.com%C_RESET%
        pause
        exit /b 1
    ) else (
        echo %C_GREEN%  [OK] Ollama is now ready.%C_RESET%
    )
) else (
    echo %C_GREEN%  [OK] Ollama is ready.%C_RESET%
)
echo.

:: 6. Start JARVIS
echo %C_CYAN%============================================================
echo %C_CYAN%  Starting JARVIS V20...
echo %C_CYAN%============================================================
echo %C_RESET%
echo.

python main.py %*
set EXIT_CODE=%errorlevel%

:: End with pause and exit code
echo.
if %EXIT_CODE% equ 0 (
    echo %C_GREEN%============================================================
    echo %C_GREEN%  JARVIS exited cleanly.
    echo %C_GREEN%============================================================
) else (
    echo %C_RED%============================================================
    echo %C_RED%  JARVIS exited with error code: %EXIT_CODE%
    echo %C_RED%============================================================
)

echo.
pause
exit /b %EXIT_CODE%
