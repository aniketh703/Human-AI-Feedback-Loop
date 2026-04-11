@echo off
echo ============================================
echo    Starting Rasa Chatbot Project
echo ============================================
echo.

:: Set the website URL (change this to your desired website)
set WEBSITE_URL=https://rasa.com

:: Configuration options
:: Set AUTO_SCRAPE=true to enable website scraping (may take time)
set AUTO_SCRAPE=false
set AUTO_TRAIN=false
set MAX_PAGES=30

:: Get the directory where this script is located
set PROJECT_DIR=%~dp0

:: Check for command line arguments
if "%1"=="--scrape" set AUTO_SCRAPE=true
if "%1"=="--scrape" set AUTO_TRAIN=true
if "%1"=="--skip-scrape" set AUTO_SCRAPE=false
if "%1"=="--skip-scrape" set AUTO_TRAIN=false
if "%1"=="--no-train" set AUTO_TRAIN=false
if "%2"=="--no-train" set AUTO_TRAIN=false

:: ============================================
:: STEP 1: Website Scraping & Training Data Generation
:: ============================================
if "%AUTO_SCRAPE%"=="true" (
    echo [1/6] Scraping website and generating training data...
    echo       URL: %WEBSITE_URL%
    echo       Max Pages: %MAX_PAGES%
    echo.
    
    cd /d %PROJECT_DIR%rasa-backend
    call venv\Scripts\activate.bat
    
    :: Run the website-to-training pipeline
    python website_to_training.py %WEBSITE_URL% --max-pages %MAX_PAGES%
    
    if errorlevel 1 (
        echo.
        echo [WARNING] Website scraping failed or no new data generated.
        echo           Continuing with existing training data...
        echo.
    ) else (
        echo.
        echo [SUCCESS] Training data generated from website!
        echo.
    )
    
    :: Check if we should auto-train
    if "%AUTO_TRAIN%"=="true" (
        echo [2/6] Training Rasa model...
        echo       This may take a few minutes...
        echo.
        rasa train
        
        if errorlevel 1 (
            echo.
            echo [WARNING] Training failed. Using existing model.
            echo.
        ) else (
            echo.
            echo [SUCCESS] Model trained successfully!
            echo.
        )
    ) else (
        echo [2/6] Skipping auto-training (use --train flag to enable)
        echo.
    )
) else (
    echo [1/6] Skipping website scraping (--skip-scrape flag detected)
    echo [2/6] Skipping training
    echo.
)

:: ============================================
:: STEP 2: Start Services
:: ============================================

echo [3/6] Starting Action Server...
start "Rasa Action Server" cmd /k "cd /d %PROJECT_DIR%rasa-backend && call venv\Scripts\activate.bat && set WEBSITE_URL=%WEBSITE_URL% && rasa run actions"

:: Wait for action server to start
timeout /t 5 /nobreak > nul

echo [4/6] Starting Rasa Server...
start "Rasa Server" cmd /k "cd /d %PROJECT_DIR%rasa-backend && call venv\Scripts\activate.bat && set WEBSITE_URL=%WEBSITE_URL% && rasa run --enable-api --cors *"

:: Wait for rasa server to start
timeout /t 10 /nobreak > nul

echo [5/6] Starting API Server (Agent Dashboard)...
start "API Server" cmd /k "cd /d %PROJECT_DIR%rasa-backend && call venv\Scripts\activate.bat && python api_server.py"

:: Wait for API server to start
timeout /t 3 /nobreak > nul

echo [6/6] Starting React Frontend...
start "React Frontend" cmd /k "cd /d %PROJECT_DIR%react-frontend && npm start"

echo.
echo ============================================
echo    All services are starting!
echo ============================================
echo.
echo    Action Server: http://localhost:5055
echo    Rasa Server:   http://localhost:5005
echo    API Server:    http://localhost:5001
echo    Frontend:      http://localhost:3000
echo.
echo    Website URL:   %WEBSITE_URL%
echo.
echo ============================================
echo    USAGE OPTIONS:
echo ============================================
echo    start_all.bat              - Just start services (default)
echo    start_all.bat --scrape     - Scrape website + Train + Start
echo    start_all.bat --scrape --no-train - Scrape but skip training
echo ============================================
echo.
echo    Press any key to exit this window...
echo    (The servers will keep running)
echo ============================================
pause > nul
