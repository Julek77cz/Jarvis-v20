@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ======================================================================
::  JARVIS V19 - Universal Setup Installer (Windows)
::  Hardware Auto-Detect Edition
::  Enhanced with comprehensive error handling and debug pauses
:: ======================================================================

:: ======================================================================
:: DEBUG STARTUP - Shows script is running before anything else
:: ======================================================================
echo ========================================
echo JARVIS SETUP SCRIPT STARTED
echo ========================================
echo Current directory: %CD%
echo Script location: %~f0
echo ========================================
pause

:: --- Configuration ----------------------------------------------------
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
cd /d "%PROJECT_DIR%" 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Cannot change to project directory: %PROJECT_DIR%"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)

set "VENV_DIR=%PROJECT_DIR%\.venv"
set "PYTHON_MIN=3.10"
set "OLLAMA_URL=http://localhost:11434"

:: Always include these models
set "BASE_MODELS=nomic-embed-text jobautomation/OpenEuroLLM-Czech:latest"
set "SELECTED_MODEL="

:: --- Colors for Windows (disabled for CMD compatibility) ---
set "RESET="
set "RED="
set "GREEN="
set "YELLOW="
set "CYAN="
set "BLUE="

goto :main

:: --- Helper Functions --------------------------------------------------
:echo_color
set "color=%~1"
set "text=%~2"
set "text=%text:"=%"
echo %color%%text%%RESET%
goto :eof

:detect_hardware
:: Global variables for hardware
set "VRAM_GB=0"
set "RAM_GB=0"
set "GPU_NAME=Neznama nebo zadna GPU"

:: Detect VRAM using nvidia-smi
for /f "tokens=*" %%a in ('nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2^>nul') do (
    set /a VRAM_MB=%%a
    set /a VRAM_GB=VRAM_MB/1024
)

:: Detect GPU name
for /f "tokens=*" %%a in ('nvidia-smi --query-gpu=name --format=csv,noheader 2^>nul') do (
    set "GPU_NAME=%%a"
    goto :ram_detection
)

:ram_detection
:: Detect RAM using wmic
for /f "tokens=2 delims==" %%a in ('wmic OS get TotalVisibleMemorySize /value 2^>nul ^| find "TotalVisibleMemorySize"') do (
    set /a RAM_KB=%%a
    set /a RAM_GB=RAM_KB/1048576
)
goto :eof

:select_model
echo.
call :echo_color "%CYAN%" "======================================================================"
call :echo_color "%CYAN%" "Hardware Detekce:"
call :echo_color "%CYAN%" "======================================================================"
echo   GPU:  %GPU_NAME%
if %VRAM_GB% gtr 0 (
    echo   VRAM: %VRAM_GB% GB
) else (
    echo   VRAM: Nedetekovano (NVIDIA driver chybi)
)
if %RAM_GB% gtr 0 (
    echo   RAM:  %RAM_GB% GB
)
echo.
call :echo_color "%CYAN%" "======================================================================"
call :echo_color "%CYAN%" "Doporucone modely pro tvuj system:"
call :echo_color "%CYAN%" "======================================================================"
echo.

set INDEX=1

if %VRAM_GB% lss 4 (
    echo   [!INDEX!] qwen2.5:3b-instruct
    echo       Lehky a rychly model ^(idealni pro slabsi VRAM^)
    echo.
    set "REC_!INDEX!=qwen2.5:3b-instruct"
    set /a INDEX+=1
)
if %VRAM_GB% geq 4 (
    if %VRAM_GB% lss 6 (
        echo   [!INDEX!] qwen2.5:7b-instruct
        echo       Dobra rovnovaha mezi rychlosti a kvalitou
        echo.
        set "REC_!INDEX!=qwen2.5:7b-instruct"
        set /a INDEX+=1
        echo   [!INDEX!] llama3.1:8b-instruct-q4_K_M
        echo       Vyssi kvalita uvazovani
        echo.
        set "REC_!INDEX!=llama3.1:8b-instruct-q4_K_M"
        set /a INDEX+=1
    )
)
if %VRAM_GB% geq 6 (
    if %VRAM_GB% lss 9 (
        echo   [!INDEX!] llama3.1:8b-instruct
        echo       DOPORUCENO - Nejlepsi pro 8GB VRAM ^(Ryzen-Beast^)
        echo.
        set "REC_!INDEX!=llama3.1:8b-instruct"
        set /a INDEX+=1
        echo   [!INDEX!] qwen2.5:7b-instruct
        echo       Rychlejsi alternativa pro programovani
        echo.
        set "REC_!INDEX!=qwen2.5:7b-instruct"
        set /a INDEX+=1
    )
)
if %VRAM_GB% geq 9 (
    echo   [!INDEX!] llama3.1:8b-instruct
    echo       Rychly a velmi schopny
    echo.
    set "REC_!INDEX!=llama3.1:8b-instruct"
    set /a INDEX+=1
    echo   [!INDEX!] mistral-nemo:12b-instruct-q4_K_M
    echo       Vyssi kvalita s 12B parametry
    echo.
    set "REC_!INDEX!=mistral-nemo:12b-instruct-q4_K_M"
    set /a INDEX+=1
)

set CUSTOM_CHOICE=%INDEX%
echo   [%CUSTOM_CHOICE%] Vlastni - Zadej jmeno jineho modelu
echo.

:selection_loop
set /p CHOICE="Vyber [1-%CUSTOM_CHOICE%]: "

echo %CHOICE%| findstr /r "^[0-9][0-9]*$" >nul
if errorlevel 1 (
    call :echo_color "%RED%" "  Zadej platne cislo!"
    goto selection_loop
)
if %CHOICE% lss 1 goto selection_loop
if %CHOICE% gtr %CUSTOM_CHOICE% goto selection_loop

if %CHOICE% equ %CUSTOM_CHOICE% (
    :custom_model_loop
    set /p CUSTOM_MODEL="Zadej jmeno (napr. llama3.1:8b-instruct): "
    if "!CUSTOM_MODEL!"=="" goto custom_model_loop
    set "SELECTED_MODEL=!CUSTOM_MODEL!"
) else (
    for %%i in (!CHOICE!) do set "SELECTED_MODEL=!REC_%%i!"
)

call :echo_color "%GREEN%" "  Vybrano: !SELECTED_MODEL!"
goto :eof

:update_user_config
set "model=%~1"
if not exist "%PROJECT_DIR%\jarvis_config" mkdir "%PROJECT_DIR%\jarvis_config" 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Cannot create jarvis_config directory"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)
set "config_file=%PROJECT_DIR%\jarvis_config\user_config.py"

(
echo.
echo """ User Configuration Override for JARVIS
echo.
echo This file was auto-generated by the setup script based on your
echo detected hardware and selected model preferences.
echo """ 
echo.
echo def apply_user_config^(^):
echo     """ Apply user-selected model configuration. """
echo     import jarvis_config as _cfg
echo.
echo     # Override with user-selected models
echo     _cfg.MODELS["planner"] = "%model%"
echo     _cfg.MODELS["verifier"] = "%model%"
echo     _cfg.MODELS["reasoner"] = "%model%"
echo.
echo     # Note: MODELS["czech_gateway"] remains jobautomation/OpenEuroLLM-Czech:latest
) > "%config_file%" 2>&1

if errorlevel 1 (
    call :echo_color "%RED%" "  Nepodarilo se ulozit konfiguraci!"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)
call :echo_color "%GREEN%" "  Konfigurace ulozena: %config_file%"
goto :eof

:check_python
where python >nul 2>&1
if %errorlevel% equ 0 (
    python --version 2>nul | findstr /r "Python [3]\.[0-9]*" >nul
    if !errorlevel! equ 0 (
        set "PYTHON=python"
        exit /b 0
    )
)
where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON=py"
    exit /b 0
)
exit /b 1

:get_python_version
for /f "tokens=2" %%v in ('%PYTHON% --version 2^>^&1') do set "PYTHON_VERSION=%%v"
goto :eof

:check_ollama_running
curl -s "%OLLAMA_URL%/api/tags" >nul 2>&1
exit /b %errorlevel%

:wait_for_ollama
echo.
call :echo_color "%YELLOW%" "  Cekam na sluzbu Ollama..."
set "OLLAMA_READY=0"
for /L %%i in (1,1,30) do (
    curl -s "%OLLAMA_URL%/api/tags" >nul 2>&1
    if !errorlevel! equ 0 (
        set "OLLAMA_READY=1"
        goto :eof
    )
    timeout /t 2 /nobreak >nul
)
exit /b %errorlevel%

:create_venv
if exist "%VENV_DIR%\Scripts\activate.bat" (
    call :echo_color "%BLUE%" "  Virtualni prostredi jiz existuje"
    exit /b 0
)
call :echo_color "%CYAN%" "  Vytvarim virtualni prostredi..."
%PYTHON% -m venv "%VENV_DIR%" 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Failed to create virtual environment"
    echo Error code: !errorlevel!
    echo Command: %PYTHON% -m venv "%VENV_DIR%"
    pause
    exit /b 1
)
exit /b 0

:activate_venv
set "PATH=%VENV_DIR%\Scripts;%PATH%"
goto :eof

:install_dependencies
call :echo_color "%CYAN%" "  Instaluji Python balicky..."
%PYTHON% -m pip install --upgrade pip -q 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Failed to upgrade pip"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)
%PYTHON% -m pip install -r "%PROJECT_DIR%\requirements.txt" -q 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Failed to install dependencies from requirements.txt"
    echo Error code: !errorlevel!
    echo Check requirements.txt: "%PROJECT_DIR%\requirements.txt"
    pause
    exit /b 1
)
exit /b 0

:pull_model
set "model=%~1"
call :echo_color "%CYAN%" "  Stahuji model: %model% (tohle chvili potrva)..."
call :echo_color "%CYAN%" "  ========================================================"
ollama pull %model% 2>&1
if !errorlevel! equ 0 (
    call :echo_color "%GREEN%" "  ✓ Model nainstalovan: %model%"
) else (
    call :echo_color "%RED%" "  ✗ Chyba stahovani: %model%"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)
goto :eof

:create_data_dirs
call :echo_color "%CYAN%" "  Vytvarim pracovni slozky..."
if not exist "%PROJECT_DIR%\jarvis_data\memory" mkdir "%PROJECT_DIR%\jarvis_data\memory" 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Cannot create jarvis_data\memory directory"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)
if not exist "%PROJECT_DIR%\jarvis_data\chromadb" mkdir "%PROJECT_DIR%\jarvis_data\chromadb" 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Cannot create jarvis_data\chromadb directory"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)
if not exist "%PROJECT_DIR%\jarvis_data\wal" mkdir "%PROJECT_DIR%\jarvis_data\wal" 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Cannot create jarvis_data\wal directory"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)
if not exist "%PROJECT_DIR%\jarvis_data\procedural" mkdir "%PROJECT_DIR%\jarvis_data\procedural" 2>&1
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Cannot create jarvis_data\procedural directory"
    echo Error code: !errorlevel!
    pause
    exit /b 1
)
goto :eof

:print_banner
echo.
echo ======================================================================
echo          JARVIS V19 - Universal Setup Installer
echo                 Windows Hardware Auto-Detect
echo ======================================================================
echo.
goto :eof

:: --- MAIN SCRIPT ------------------------------------------------------
:main
call :print_banner

:: Step 1: Check Python
call :echo_color "%CYAN%" "[1/7] Kontrola Pythonu..."
call :check_python
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Python 3.10+ nenalezen!"
    echo Error code: !errorlevel!
    echo.
    echo Please install Python 3.10 or higher from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
call :get_python_version
call :echo_color "%GREEN%" "  ✓ Python !PYTHON_VERSION! pripraven"
echo.

:: Step 2: Create venv
call :echo_color "%CYAN%" "[2/7] Priprava prostredi (venv)..."
call :create_venv
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Virtual environment creation failed!"
    pause
    exit /b 1
)
call :activate_venv
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Failed to activate virtual environment!"
    pause
    exit /b 1
)
call :echo_color "%GREEN%" "  ✓ Virtualni prostredi pripraveno"
echo.

:: Step 3: Install dependencies
call :echo_color "%CYAN%" "[3/7] Instalace knihoven..."
call :install_dependencies
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Dependency installation failed!"
    pause
    exit /b 1
)
call :echo_color "%GREEN%" "  ✓ Knihovny nainstalovany"
echo.

:: Step 4: Check Ollama
call :echo_color "%CYAN%" "[4/7] Kontrola sluzby Ollama..."
call :check_ollama_running
if !errorlevel! neq 0 (
    call :echo_color "%YELLOW%" "  Startuji Ollamu..."
    start "" ollama serve 2>&1
    if !errorlevel! neq 0 (
        call :echo_color "%RED%" "ERROR: Failed to start Ollama service!"
        echo Error code: !errorlevel!
        echo.
        echo Please install Ollama from: https://ollama.com/download
        pause
        exit /b 1
    )
    call :wait_for_ollama
    if !errorlevel! neq 0 (
        call :echo_color "%RED%" "ERROR: Ollama failed to start or is not responding!"
        echo Error code: !errorlevel!
        pause
        exit /b 1
    )
)
call :echo_color "%GREEN%" "  ✓ Ollama bezi"
echo.

:: Step 5: Detect hardware and select model
call :echo_color "%CYAN%" "[5/7] Detekce hardwaru a vyber modelu..."
call :detect_hardware
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Hardware detection failed!"
    pause
    exit /b 1
)
call :select_model
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Model selection failed!"
    pause
    exit /b 1
)
echo.

:: Step 6: Download models
call :echo_color "%CYAN%" "[6/7] Stahovani LLM modelu..."
echo.
for %%m in (%BASE_MODELS%) do (
    call :pull_model "%%m"
    if !errorlevel! neq 0 (
        call :echo_color "%RED%" "ERROR: Failed to download model: %%m"
        pause
        exit /b 1
    )
)
echo.
call :pull_model "%SELECTED_MODEL%"
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Failed to download selected model!"
    pause
    exit /b 1
)
echo.
call :update_user_config "%SELECTED_MODEL%"
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Failed to update user configuration!"
    pause
    exit /b 1
)
echo.

:: Step 7: Create data directories
call :echo_color "%CYAN%" "[7/7] Dokoncovani instalace..."
call :create_data_dirs
if !errorlevel! neq 0 (
    call :echo_color "%RED%" "ERROR: Failed to create data directories!"
    pause
    exit /b 1
)
call :echo_color "%GREEN%" "  ✓ Pracovni slozky vytvoreny"
echo.

:: Success!
echo.
call :echo_color "%GREEN%" "======================================================================"
call :echo_color "%GREEN%" "  INSTALACE JARVISE JE KOMPLETNI!"
call :echo_color "%GREEN%" "======================================================================"
echo.
echo   - Tvuj mozek: %SELECTED_MODEL%
echo   - Prekladac:  OpenEuroLLM-Czech:latest
echo.
echo   Nyni spust: start_jarvis.bat
echo.
echo.
echo ========================================
echo SETUP COMPLETED SUCCESSFULLY
echo ========================================
pause
exit /b 0
