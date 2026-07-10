@echo off
REM ============================================================
REM Image Toolkit - exe build script
REM Run this file on a Windows PC where venv already exists.
REM Usage: double-click this file, or run "build_exe.bat" in the project folder.
REM ============================================================

echo [1/5] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not find venv. Please run "python -m venv venv" and "pip install -r requirements.txt" first.
    pause
    exit /b 1
)

echo [2/5] Patching streamlit-cropper (keeps the crop box inside the image preview)...
python patch_streamlit_cropper.py
if errorlevel 1 (
    echo ERROR: Failed to patch streamlit-cropper.
    pause
    exit /b 1
)

echo [3/5] Installing PyInstaller into the virtual environment...
pip install --quiet pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

echo [4/5] Cleaning up previous build files...
echo Closing any running instance of the program (if any)...
taskkill /IM ImageToolkit.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist dist (
    echo.
    echo ERROR: Could not remove the dist folder. A file inside may still be in use.
    echo Please close ImageToolkit.exe manually via Task Manager, then run this script again.
    pause
    exit /b 1
)
if exist ImageToolkit.spec del /q ImageToolkit.spec

echo [5/5] Building the exe file... (this can take a few minutes)
pyinstaller --onefile --noconsole --name ImageToolkit --splash "splash.png" --collect-all streamlit --collect-all streamlit_cropper --collect-all rembg --collect-all onnxruntime --collect-all pymatting --collect-all scipy --collect-all pooch --add-data "app.py;." --add-data "home.py;." --add-data "background_remover.py;." --add-data "image_resizer.py;." --add-data "file_handler.py;." --add-data "image_cropper.py;." --add-data "utils.py;." --add-data "app_pages;app_pages" run_app.py

if errorlevel 1 (
    echo.
    echo Build failed. Please check the log above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Build complete!
echo Output file: dist\ImageToolkit.exe
echo You can rename this file to Korean afterward if you like,
echo then share this single file with other users.
echo ============================================================
pause
