#!/bin/bash

# ElasticBot Backend Setup Script
# This script automates the initial setup process

set -e

echo "========================================="
echo "ElasticBot Backend Setup"
echo "========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "❌ Python $required_version or higher is required. Found: $python_version"
    exit 1
fi
echo "✅ Python $python_version detected"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python -m venv venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi
echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Setup environment file
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo "⚠️  Please edit .env with your credentials before running migrations"
    echo ""
else
    echo "ℹ️  .env file already exists"
    echo ""
fi

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs
echo "✅ Logs directory created"
echo ""

# Run migrations
read -p "Do you want to run database migrations now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running migrations..."
    python manage.py makemigrations
    python manage.py migrate
    echo "✅ Migrations completed"
    echo ""
fi

# Create superuser
read -p "Do you want to create a superuser now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Creating superuser..."
    python manage.py createsuperuser
    echo "✅ Superuser created"
    echo ""
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput
echo "✅ Static files collected"
echo ""

echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your credentials"
echo "2. Run: python manage.py runserver"
echo "3. Run Celery worker: celery -A base worker -l info"
echo "4. Run Celery beat: celery -A base beat -l info"
echo ""
echo "Access the application at: http://localhost:8000"
echo "Access admin panel at: http://localhost:8000/admin"
echo ""
