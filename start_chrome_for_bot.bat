@echo off
echo Killing existing Chrome...
taskkill /F /IM chrome.exe >nul 2>&1

timeout /t 1 >nul

echo Starting Chrome in Debug Mode...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
--remote-debugging-port=9222 ^
--user-data-dir="C:\ChromeDebug" ^
--profile-directory="Default"

echo.
echo Chrome Debug Mode Started on Port 9222
echo Test at: http://127.0.0.1:9222/json/version
pause
