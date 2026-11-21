@echo off
setlocal
REM ============================================================
REM  Upload this project (code + data) to GitHub:
REM  https://github.com/NiharikaSeela/cvaprject
REM  The online app then updates by itself:
REM  https://cvaprject-27dcmco8ektvdyhi4zkiwt.streamlit.app/
REM
REM  Double-click this file, or run  .\push.bat  in this folder.
REM ============================================================
cd /d "%~dp0"

echo [1/4] Saving the database into one file...
python -c "import sqlite3,os; p='data/water_quality.db'; c=sqlite3.connect(p) if os.path.exists(p) else None; c and c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c and c.close(); print('      database ready')"

echo [2/4] Copying theme settings for the online app...
if not exist "..\.streamlit" mkdir "..\.streamlit"
copy /Y ".streamlit\config.toml" "..\.streamlit\config.toml" >nul

REM Git lives one level up (in Term4) so that GitHub keeps the path
REM water_quality/app.py, which the online app is set to run.
cd ..
if not exist ".git" (
    echo [setup] First time: connecting this folder to GitHub...
    > .gitignore echo /*
    >> .gitignore echo !/.gitignore
    >> .gitignore echo !/water_quality/
    >> .gitignore echo !/.streamlit/
    git init -q
    git branch -M main
    git remote add origin https://github.com/NiharikaSeela/cvaprject.git
)

echo [3/4] Saving changes...
git add -A
git commit -q -m "Update from water_quality folder"

echo [4/4] Uploading to GitHub...
git push --force -u origin main
if errorlevel 1 (
    echo.
    echo Upload FAILED. Copy the messages above and send them to Claude.
) else (
    echo.
    echo Done. The online app updates in about a minute.
)
pause
