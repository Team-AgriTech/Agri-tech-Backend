# Flask Application Startup Script
# This script activates the virtual environment and starts the Flask development server

Write-Host "Starting Flask Application..." -ForegroundColor Green

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Set Flask environment variables
Write-Host "Setting Flask environment variables..." -ForegroundColor Yellow
$env:FLASK_ENV = "development"
$env:FLASK_APP = "app.py"

# Start Flask application
Write-Host "Starting Flask development server..." -ForegroundColor Green
flask run

Write-Host "Flask application stopped." -ForegroundColor Red