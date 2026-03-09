@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "PROJECT_DIR=%CD%"
set "VENV_DIR=%PROJECT_DIR%\.venv"
set "PYTHON_MIN=3.10"
set "OLLAMA_URL=http://localhost:11434"
set "BASE_MODELS=nomic-embed-text jobautomation/OpenEuroLLM-Czech:latest"
set "SELECTED_MODEL="
set "DEFAULT_RAM_GB=8"

for /f %%a in ('powershell -NoProfile -Command "$esc=[char]27; Write-Output $esc"') do set "ESC=%%a"
if not defined ESC set "ESC="

set "RESET=%ESC%[0m"
set "BOLD=%ESC%[1m"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "BLUE=%ESC%[94m"
set "MAGENTA=%ESC%[95m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"

goto :main

:echo_color
set "color=%~1"
set "text=%~2"
echo(!color!!text!!RESET!
goto :eof

:section
echo.
call :echo_color "%CYAN%" "%~1"
goto :eof

:progress
call :echo_color "%BLUE%" "[→] %~1"
goto :eof

:success
call :echo_color "%GREEN%" "[✓] %~1"
goto :eof

:warn
call :echo_color "%YELLOW%" "[!] %~1"
goto :eof

:error_msg
call :echo_color "%RED%" "[×] %~1"
goto :eof

:print_banner
echo.
call :echo_color "%MAGENTA%" "╔══════════════════════════════════════════════════════════════════════╗"
call :echo_color "%MAGENTA%" "║                        🤖 JARVIS V20 SETUP                         ║"
call :echo_color "%MAGENTA%" "║                 Windows Smart Installer & Detector                ║"
call :echo_color "%MAGENTA%" "╚══════════════════════════════════════════════════════════════════════╝"
call :echo_color "%CYAN%"    "      ✨ Barevne UI  •  Automaticka detekce HW  •  Ollama ready"
echo.
goto :eof

:detect_hardware
set "VRAM_GB=0"
set "RAM_GB=%DEFAULT_RAM_GB%"
set "GPU_NAME=No GPU detected"

for /f "usebackq delims=" %%a in (`nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2^>nul`) do (
    if not defined VRAM_MB set "VRAM_MB=%%a"
)
if defined VRAM_MB (
    set /a VRAM_GB=VRAM_MB/1024
)

for /f "usebackq delims=" %%a in (`nvidia-smi --query-gpu=name --format=csv,noheader 2^>nul`) do (
    if not defined GPU_NAME_FOUND (
        set "GPU_NAME=%%a"
        set "GPU_NAME_FOUND=1"
    )
)

for /f "tokens=2" %%a in ('powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1048576" 2^>nul') do set "RAM_MB=%%a"
if defined RAM_MB (
    for /f "tokens=1 delims=." %%b in ("%RAM_MB%") do set /a RAM_GB=%%b/1024
)

if not defined RAM_MB (
    for /f "tokens=2 delims=:" %%a in ('systeminfo ^| findstr /C:"Total Physical Memory"') do set "RAM_LINE=%%a"
    if defined RAM_LINE (
        set "RAM_LINE=!RAM_LINE: =!"
        set "RAM_LINE=!RAM_LINE:,=!"
        for /f "tokens=1 delims=M" %%a in ("!RAM_LINE!") do set "RAM_MB=%%a"
        if defined RAM_MB set /a RAM_GB=RAM_MB/1024
    )
)

if not defined RAM_GB set "RAM_GB=%DEFAULT_RAM_GB%"
if %RAM_GB% leq 0 set "RAM_GB=%DEFAULT_RAM_GB%"
if %VRAM_GB% leq 0 set "VRAM_GB=0"
set "VRAM_MB="
set "GPU_NAME_FOUND="
set "RAM_MB="
set "RAM_LINE="
goto :eof

:select_model
echo.
call :echo_color "%CYAN%" "══════════════════════════════════════════════════════════════════════"
call :echo_color "%CYAN%" "🖥  Detekce hardwaru"
call :echo_color "%CYAN%" "══════════════════════════════════════════════════════════════════════"
echo   GPU:  %GPU_NAME%
if %VRAM_GB% gtr 0 (
    echo   VRAM: %VRAM_GB% GB
) else (
    echo   VRAM: Nedetekovano ^(nebo bez NVIDIA GPU^)
)
echo   RAM:  %RAM_GB% GB
echo.
call :echo_color "%CYAN%" "Doporucene modely pro tvuj system:"
echo.

set INDEX=1

if %VRAM_GB% lss 4 (
    echo   [!INDEX!] qwen2.5:3b-instruct
    echo       ⚡ Lehk y, rychly a vhodny pro slabsi hardware
    echo.
    set "REC_!INDEX!=qwen2.5:3b-instruct"
    set /a INDEX+=1
)
if %VRAM_GB% geq 4 if %VRAM_GB% lss 6 (
    echo   [!INDEX!] qwen2.5:7b-instruct
    echo       ⚖️  Dobra rovnovaha mezi rychlosti a kvalitou
    echo.
    set "REC_!INDEX!=qwen2.5:7b-instruct"
    set /a INDEX+=1
    echo   [!INDEX!] llama3.1:8b-instruct-q4_K_M
    echo       🧠 Lepsi kvalita pri rozumne spotrebe VRAM
    echo.
    set "REC_!INDEX!=llama3.1:8b-instruct-q4_K_M"
    set /a INDEX+=1
)
if %VRAM_GB% geq 6 if %VRAM_GB% lss 9 (
    echo   [!INDEX!] llama3.1:8b-instruct
    echo       ✅ DOPORUCENO pro 8GB VRAM
    echo.
    set "REC_!INDEX!=llama3.1:8b-instruct"
    set /a INDEX+=1
    echo   [!INDEX!] qwen2.5:7b-instruct
    echo       ⚡ Rychlejsi alternativa pro coding workflow
    echo.
    set "REC_!INDEX!=qwen2.5:7b-instruct"
    set /a INDEX+=1
)
if %VRAM_GB% geq 9 (
    echo   [!INDEX!] llama3.1:8b-instruct
    echo       🚀 Rychly a velmi schopny model
    echo.
    set "REC_!INDEX!=llama3.1:8b-instruct"
    set /a INDEX+=1
    echo   [!INDEX!] mistral-nemo:12b-instruct-q4_K_M
    echo       🧩 Vyssi kvalita s 12B parametry
    echo.
    set "REC_!INDEX!=mistral-nemo:12b-instruct-q4_K_M"
    set /a INDEX+=1
)

set CUSTOM_CHOICE=%INDEX%
echo   [%CUSTOM_CHOICE%] ✍️  Vlastni model
echo.

:selection_loop
set /p CHOICE="Vyber [1-%CUSTOM_CHOICE%]: "
echo %CHOICE%| findstr /r "^[0-9][0-9]*$" >nul
if errorlevel 1 (
    call :error_msg "Zadej platne cislo."
    goto selection_loop
)
if %CHOICE% lss 1 goto selection_loop
if %CHOICE% gtr %CUSTOM_CHOICE% goto selection_loop

if %CHOICE% equ %CUSTOM_CHOICE% (
    :custom_model_loop
    set /p CUSTOM_MODEL="Zadej jmeno modelu: "
    if "!CUSTOM_MODEL!"=="" goto custom_model_loop
    set "SELECTED_MODEL=!CUSTOM_MODEL!"
) else (
    call set "SELECTED_MODEL=%%REC_%CHOICE%%%"
)

call :success "Vybrano: !SELECTED_MODEL!"
goto :eof

:update_user_config
set "model=%~1"
if not exist "%PROJECT_DIR%\jarvis_config" mkdir "%PROJECT_DIR%\jarvis_config"
set "config_file=%PROJECT_DIR%\jarvis_config\user_config.py"
(
echo """
echo User Configuration Override for JARVIS
echo.
echo This file was auto-generated by the setup script based on your
echo detected hardware and selected model preferences.
echo """
echo.
echo def apply_user_config^(^):
echo     import jarvis_config as _cfg
echo.
echo     _cfg.MODELS["planner"] = "%model%"
echo     _cfg.MODELS["verifier"] = "%model%"
echo     _cfg.MODELS["reasoner"] = "%model%"
) > "%config_file%"
if errorlevel 1 (
    call :error_msg "Nepodarilo se ulozit konfiguraci."
    exit /b 1
)
call :success "Konfigurace ulozena: %config_file%"
goto :eof

:check_python
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON=python"
    exit /b 0
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
call :warn "Cekam na sluzbu Ollama..."
for /L %%i in (1,1,30) do (
    curl -s "%OLLAMA_URL%/api/tags" >nul 2>&1
    if !errorlevel! equ 0 exit /b 0
    timeout /t 2 /nobreak >nul
)
exit /b 1

:create_venv
if exist "%VENV_DIR%\Scripts\activate.bat" (
    call :success "Virtualni prostredi uz existuje"
    exit /b 0
)
call :progress "Vytvarim virtualni prostredi..."
%PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 exit /b 1
exit /b 0

:activate_venv
set "PATH=%VENV_DIR%\Scripts;%PATH%"
goto :eof

:install_dependencies
call :progress "Instaluji Python balicky a colorama podporu..."
%PYTHON% -m pip install --upgrade pip
if errorlevel 1 exit /b 1
%PYTHON% -m pip install -r "%PROJECT_DIR%\requirements.txt"
if errorlevel 1 exit /b 1
exit /b 0

:pull_model
set "model=%~1"
call :progress "Stahuji model %model%..."
ollama pull %model%
if errorlevel 1 exit /b 1
call :success "Model pripraven: %model%"
goto :eof

:create_data_dirs
call :progress "Vytvarim pracovni slozky..."
if not exist "%PROJECT_DIR%\jarvis_data\memory" mkdir "%PROJECT_DIR%\jarvis_data\memory"
if not exist "%PROJECT_DIR%\jarvis_data\orchestrator" mkdir "%PROJECT_DIR%\jarvis_data\orchestrator"
if not exist "%PROJECT_DIR%\jarvis_data\chromadb" mkdir "%PROJECT_DIR%\jarvis_data\chromadb"
if not exist "%PROJECT_DIR%\jarvis_data\knowledge_graph" mkdir "%PROJECT_DIR%\jarvis_data\knowledge_graph"
if not exist "%PROJECT_DIR%\jarvis_data\wal" mkdir "%PROJECT_DIR%\jarvis_data\wal"
if not exist "%PROJECT_DIR%\jarvis_data\procedural" mkdir "%PROJECT_DIR%\jarvis_data\procedural"
if errorlevel 1 exit /b 1
call :success "Pracovni slozky jsou pripravene"
goto :eof

:main
call :print_banner

call :section "[1/7] Kontrola Pythonu"
call :check_python
if errorlevel 1 (
    call :error_msg "Python 3.10+ nebyl nalezen v PATH."
    echo Nainstaluj Python z https://www.python.org/downloads/
    pause
    exit /b 1
)
call :get_python_version
call :success "Python !PYTHON_VERSION! pripraven"

call :section "[2/7] Virtualni prostredi"
call :create_venv
if errorlevel 1 (
    call :error_msg "Nepodarilo se vytvorit virtualni prostredi."
    pause
    exit /b 1
)
call :activate_venv
call :success "Virtualni prostredi aktivovano"

call :section "[3/7] Instalace zavislosti"
call :install_dependencies
if errorlevel 1 (
    call :error_msg "Instalace Python balicku selhala."
    pause
    exit /b 1
)
call :success "Knihovny byly nainstalovany"

call :section "[4/7] Kontrola Ollamy"
call :check_ollama_running
if errorlevel 1 (
    call :warn "Ollama nebezi. Pokousim se ji spustit na pozadi..."
    start "" ollama serve
    call :wait_for_ollama
    if errorlevel 1 (
        call :error_msg "Ollama se nepodarilo spustit."
        echo Nainstaluj Ollama z https://ollama.com/download
        pause
        exit /b 1
    )
)
call :success "Ollama je pripravena"

call :section "[5/7] Detekce hardwaru"
call :detect_hardware
if %RAM_GB% equ %DEFAULT_RAM_GB% call :warn "RAM se nepodarilo presne zjistit, pouzivam vychozi hodnotu %DEFAULT_RAM_GB% GB."
call :success "Detekce dokoncena"
call :select_model

call :section "[6/7] Stahovani modelu"
call :warn "Modely mohou mit jednotky GB, vydrz chvili."
for %%m in (%BASE_MODELS%) do (
    call :pull_model "%%m"
    if errorlevel 1 (
        call :error_msg "Nepodarilo se stahnout model %%m."
        pause
        exit /b 1
    )
)
call :pull_model "%SELECTED_MODEL%"
if errorlevel 1 (
    call :error_msg "Nepodarilo se stahnout vybrany model."
    pause
    exit /b 1
)
call :update_user_config "%SELECTED_MODEL%"
if errorlevel 1 (
    pause
    exit /b 1
)

call :section "[7/7] Dokonceni instalace"
call :create_data_dirs
if errorlevel 1 (
    call :error_msg "Nepodarilo se vytvorit datove slozky."
    pause
    exit /b 1
)

echo.
call :echo_color "%GREEN%" "╔══════════════════════════════════════════════════════════════════════╗"
call :echo_color "%GREEN%" "║                      🎉 INSTALACE DOKONCENA                        ║"
call :echo_color "%GREEN%" "╚══════════════════════════════════════════════════════════════════════╝"
echo   🧠 Vybrany model: %SELECTED_MODEL%
echo   🌍 Czech gateway: jobautomation/OpenEuroLLM-Czech:latest
echo   ▶️  Dalsi krok: spust scripts\start_jarvis.bat
echo.
pause
exit /b 0
