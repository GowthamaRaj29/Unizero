# Unizero

Unizero is a financial reconciliation MVP with three runnable parts:

- `backend/` - FastAPI API and SQLite persistence
- `ai-services/` - ingestion, mapping, reconciliation and break-analysis services
- `frontend/` - React/Vite UI

## Quick Start for Teammates

1. **Install Frontend Dependencies**:
```powershell
cd frontend
npm install
```

2. **Install Python Dependencies** (if needed):
```powershell
pip install -r backend/requirements.txt
pip install -r ai-services/requirements.txt
```

3. **Start All Services**:
On Windows, simply run `start-Unizero.bat` from the project root. It starts backend, AI services, and frontend automatically in separate windows.

To start manually in three separate terminals:

```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```powershell
cd ai-services
python -m uvicorn app:app --host 127.0.0.1 --port 8001
```

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:
- Frontend: http://127.0.0.1:5173
- Backend health: http://127.0.0.1:8000/health
- AI service health: http://127.0.0.1:8001/health

## Login Credentials

Pre-seeded verified accounts for all three roles:
- **Admin**: `testinvest@recon` / `password123`
- **Investigator**: `invest@recon` / `password123`
- **Approver**: `testapprover@recon` / `password123`

You can also register new accounts from the UI; the Admin account can approve pending registrations in the Admin Console.

## Verified Checks

These commands were run successfully:

```powershell
cd frontend
npm run build
```

```powershell
cd backend
python -m pytest -q
```

```powershell
cd ai-services
python -m pytest -q
```

Current validation result:

- Frontend production build: passed
- Backend smoke/auth tests: `2 passed`
- AI-service suite: `155 passed, 1 skipped`
