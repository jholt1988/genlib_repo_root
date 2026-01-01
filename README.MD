# genlib-web v2.3 (FastAPI + Next.js)

Structure:
- backend/ (FastAPI API + serves /outputs static)
- frontend/ (Next.js UI)

Quick start (dev):
1) Start backend:
   - cd backend
   - pip install -r requirements.txt
   - uvicorn app:app --reload --host 0.0.0.0 --port 8000

2) Start frontend:
   - cd frontend
   - npm install
   - npm run dev

Frontend talks to backend at NEXT_PUBLIC_API_BASE (default http://localhost:8000).
