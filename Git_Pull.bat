@echo off
TITLE Github Quick-Pull

echo ==========================================
echo 📌 Pulling into Branch:
:: Sirf current branch ka naam clean tarike se print karega
git branch --show-current
echo ==========================================
echo.

echo 🔄 Fetching and pulling latest changes...
git pull

:: Agar pull fail hota hai (jaise uncommitted changes ya conflict ki wajah se)
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ [ERROR] Git pull failed! 
    echo ⚠️ You might have uncommitted local changes or a merge conflict.
    pause
    exit /b
)

echo.
echo ==========================================
echo ✅ Code Pulled Successfully!
echo ==========================================
pause
