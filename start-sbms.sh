#!/bin/bash

# SBMS Setup and Start Script
# Simple Brewery Management System

echo "=== SBMS Setup and Start ==="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker..."
    
    # Update package index
    sudo apt update
    
    # Install Docker
    sudo apt install -y docker.io docker-compose
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    echo "Docker installed. You may need to log out and log back in for group changes to take effect."
    echo "Run this script again after logging back in."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "docker-compose not found, trying 'docker compose'..."
    if ! docker compose version &> /dev/null; then
        echo "Neither docker-compose nor 'docker compose' is available."
        echo "Please install Docker Compose."
        exit 1
    fi
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file with your configuration before running again."
    exit 1
fi

echo "Starting SBMS with Docker Compose..."
$COMPOSE_CMD up -d

echo ""
echo "=== SBMS Started Successfully ==="
echo "Web interface: http://localhost:8080"
echo "Database: PostgreSQL on port 5432"
echo ""
echo "To stop: $COMPOSE_CMD down"
echo "To view logs: $COMPOSE_CMD logs -f"
echo "To rebuild: $COMPOSE_CMD up -d --build"