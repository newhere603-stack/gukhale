@echo off
TITLE Github Quick-Pushing 

echo ==========================================
echo 📌 Current Branch:
:: Sirf current branch ka naam print karega (Clean look)
git branch --show-current
echo ==========================================
echo.

:: Take input for comment
set /p commit_title="Enter Commit title (Leave blank for default): "

:: Agar user sirf Enter daba de toh default message set ho jayega
if "%commit_title%"=="" (
    set commit_title=Quick update
)

echo.
echo [1/4] Pulling latest changes...
git pull
:: Agar pull fail hua (e.g., merge conflict), toh script yahi ruk jayegi
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ [ERROR] Git pull failed! Check for merge conflicts before pushing.
    pause
    exit /b
)

echo.
echo [2/4] Staging files...
:: 'git add .' saari modified, deleted aur new files ko safely stage karega (.gitignore ko respect karte hue)
git add .

echo.
echo [3/4] Committing...
git commit -m "%commit_title%"
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ [INFO] Nothing to commit (Working tree clean).
    pause
    exit /b
)

echo.
echo [4/4] Pushing to Github...
git push
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ [ERROR] Git push failed! Check your connection or permissions.
    pause
    exit /b
)

echo.
echo ==========================================
echo ✅ Code Pushed Successfully!
echo ==========================================
pause
