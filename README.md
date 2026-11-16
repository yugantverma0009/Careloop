# CareLoop

CareLoop is a synthetic-data demonstration of post-discharge patient care workflows. It includes a FastAPI backend, React frontend, MySQL schema, and ESP32 device code. It is not a medical device and is not for clinical use.

## Requirements

- Python 3.12+
- Node.js 18+ and npm
- MySQL 8+

## Setup

1. Create a MySQL database named `careloop` and import `database/schema.sql`.
2. Copy `.env.example` to `backend/.env` and set your local database credentials and secrets.
3. Install backend dependencies and load the demo dataset:

   ```sh
   python -m venv backend/env
   . backend/env/bin/activate
   pip install -r backend/requirements.txt
   python scripts/seed_demo.py
   python scripts/validate_demo.py
   ```

4. In one terminal, start the API:

   ```sh
   ./backend/env/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

5. In another terminal, start the frontend:

   ```sh
   npm --prefix frontend install
   npm --prefix frontend start
   ```

Open `http://127.0.0.1:3000` in a browser. The database seed contains synthetic demo records and credentials; change any defaults before exposing the application beyond a local environment.
