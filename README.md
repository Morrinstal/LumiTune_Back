# LumiTune Backend 🎵

Backend (server-side) of the **LumiTune** music service.  
Built with **Python + Django + Django REST Framework** and includes an **Admin Dashboard** for managing platform content (artists, tracks, playlists, etc.).
Uses **MySQL** as the main database and supports email sending via **SMTP**.

## Features
- REST API for the LumiTune frontend (React + TypeScript)
- Admin Dashboard for managing content (artists, tracks, playlists, audiobooks, podcasts)
- Media handling (covers, artist photos, audio files)
- CRUD operations for core entities
- Email support via SMTP (password reset, notifications, or feedback — depending on your implementation)

## Tech Stack
- Python
- Django
- Django REST Framework (DRF)
- MySQL (development database)
- SMTP (email)

## Getting Started

### 1) Create and activate a virtual environment
**Windows (PowerShell):**
- bash
- python -m venv venv
- venv\Scripts\Activate.ps1

**macOS / Linux:**
- python3 -m venv venv
- source venv/bin/activate

### 2) Install dependencies
- pip install -r requirements.txt

### 3) Configure environment variables
- Create a .env file in the backend root (do not commit it to git).# Database (MySQL)
- DB_NAME=
- DB_USER=
- DB_PASSWORD=
- DB_HOST=
- DB_PORT=

### SMTP (Email)
- SMTP_HOST=
- SMTP_PORT=
- SMTP_USER=
- SMTP_PASSWORD=
- DEFAULT_FROM_EMAIL=

### 4) Apply migrations
- python manage.py migrate

### 5) Create an admin user
- python manage.py createsuperuser

### 6) Run the development server
- python manage.py runserver
- Server will be available at: http://127.0.0.1:8000

**LumiTune is a learning/pet project for a music service**

