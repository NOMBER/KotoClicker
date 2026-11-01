@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title KotoClick (Котоклик)

rem Console messages are printed in English and Russian (the end user reads them).
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [!] Python not found. Install it from https://www.python.org/downloads/
    echo     and tick "Add python.exe to PATH".
    echo [!] Python не найден. Установи его с https://www.python.org/downloads/
    echo     и поставь галочку "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo First run: preparing the environment and installing libraries ...
    echo Первый запуск: готовлю окружение и ставлю библиотеки ...
    %PY% -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

rem An older environment without PySide6-Addons: install it (needed for MP3 sounds).
rem If that fails (no internet) - no problem, WAV sounds still work.
".venv\Scripts\python.exe" -c "import PySide6.QtMultimedia" >nul 2>nul
if errorlevel 1 (
    echo Installing the libraries for MP3 sounds / Доставляю библиотеки для MP3-звуков ...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo The cat is waking up / Котик просыпается ...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo [!] Something went wrong. Read the message above.
echo     If the libraries did not download, delete the .venv folder and run run.bat again.
echo [!] Что-то пошло не так. Прочитай сообщение выше.
echo     Если библиотеки не скачались, удали папку .venv и запусти run.bat ещё раз.
pause
exit /b 1
