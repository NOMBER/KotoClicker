@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title KotoClick (Котоклик) - building the .exe

rem Console messages are printed in English and Russian: the person running this
rem script is the end user, and the app's main audience reads Russian.
echo.
echo  =====================================================
echo    KotoClick: building KotoClick.exe from source
echo    Котоклик: собираем KotoClick.exe из исходников
echo  =====================================================
echo.

rem --- 1. Find Python (the py launcher from python.org is best) ---
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

rem --- 2. A separate .venv folder, so nothing is installed system-wide ---
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating the .venv virtual environment / Создаю виртуальное окружение .venv ...
    %PY% -m venv .venv || goto :error
)

echo [2/3] Installing PySide6, pynput, PyInstaller (exact versions from requirements*.txt) ...
echo       Ставлю библиотеки: PySide6, pynput, PyInstaller (точные версии из requirements*.txt) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt || goto :error
rem Strict mode (checks the SHA-256 of every file) - use instead of the line above:
rem   ".venv\Scripts\python.exe" -m pip install --require-hashes -r requirements-lock.txt

rem Temporary build files (build\ and KotoClick.spec) go to a temporary folder
rem and are deleted afterwards - only KotoClick.exe itself stays in the project folder.
set "TMPBUILD=%TEMP%\kotoclick_build_%RANDOM%"
set "ROOT=%CD%"

rem PyInstaller 6+ bundles the QtMultimedia module, its plugins
rem (plugins\multimedia) and the FFmpeg libraries by itself - they are needed for MP3/OGG/M4A.
rem So --collect-all PySide6 is NOT needed: it would make the .exe several times bigger.
rem Paths to assets are absolute: with --specpath, relative ones would resolve from the temp folder.
echo [3/3] Building KotoClick.exe (takes a couple of minutes) / Собираю KotoClick.exe (это займёт пару минут) ...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean ^
    --onefile --windowed ^
    --name KotoClick ^
    --distpath "%ROOT%" ^
    --workpath "%TMPBUILD%\work" ^
    --specpath "%TMPBUILD%" ^
    --icon "%ROOT%\assets\kotoclick.ico" ^
    --add-data "%ROOT%\assets;assets" ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    --hidden-import pynput._util.win32 ^
    --hidden-import winsound ^
    main.py
set "RC=%ERRORLEVEL%"
rem Cleanup: the temporary build folder is always deleted (on error too);
rem also build\ and the .spec files left by older build.bat versions, including the old
rem Kotoklik.spec (dist\ is not touched: it may contain your macros from an old build).
if exist "%TMPBUILD%" rmdir /s /q "%TMPBUILD%"
if exist "build\" rmdir /s /q "build"
if exist "KotoClick.spec" del /q "KotoClick.spec"
if exist "Kotoklik.spec" del /q "Kotoklik.spec"
if not "%RC%"=="0" goto :error

rem The app used to be called Kotoklik: remove the old Kotoklik.exe from the project folder
rem (only after a successful build; macros\ and sounds_custom\ next to it are left as they are).
if exist "Kotoklik.exe" (
    del /q "Kotoklik.exe" && echo  [i] Removed the old Kotoklik.exe / Удалён старый Kotoklik.exe
)

echo.
echo  Done! KotoClick.exe is right in the project folder, next to build.bat:
echo  Готово! KotoClick.exe лежит прямо в папке проекта, рядом с build.bat:
echo      %ROOT%\KotoClick.exe
echo  Run from here, it keeps macros in the macros\ folder next to itself
echo  (and trimmed sounds in sounds_custom\). If you move the .exe, move these folders too.
echo  Запущенный отсюда, он хранит макросы в папке macros\ рядом с собой
echo  (а обрезанные звуки - в sounds_custom\). Переносишь .exe - переноси и эти папки.
echo.
if exist "dist\Kotoklik.exe" (
    echo  [i] An old build is still in dist\. If it has macros ^(dist\macros^), move them
    echo      to the macros\ folder next to the new KotoClick.exe, then dist\ can be deleted.
    echo  [i] Старая сборка осталась в dist\. Если там есть макросы ^(dist\macros^),
    echo      перенеси их в папку macros\ рядом с новым KotoClick.exe, потом dist\ можно удалить.
    echo.
)
explorer /select,"%ROOT%\KotoClick.exe"
pause
exit /b 0

:error
echo.
echo [!] Something went wrong. Read the message above
echo     (most often there is no internet connection to download the libraries).
echo [!] Что-то пошло не так. Прочитай сообщение выше
echo     (чаще всего нет интернета для скачивания библиотек).
pause
exit /b 1
