# Poorvika ShopAI

## Run locally (Windows PowerShell)

Start PostgreSQL first and configure its local connection values in `backend/.env`.
Create the backend environment file from the example if needed, then set its
local PostgreSQL connection values. Do not overwrite an existing `backend/.env`.
The chatbot uses Laya for decisions, the PostgreSQL product tool for catalog
data, and Ollama for natural language responses.

### One-time setup

```powershell
cd ecom-muse-main
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

Configure PostgreSQL in `backend/.env`. Install Node.js 20 or newer for Laya.

### Terminal 1 - FastAPI (port 8000)

```powershell
cd ecom-muse-main
.\.venv\Scripts\Activate.ps1
cd backend
python run.py
```

### Terminal 2 - Laya Python V2 (port 5056)

```powershell
cd ecom-muse-main
& .\laya_v2_service\.venv\Scripts\python.exe -u .\laya_v2_service\service.py
```

The current backend expects `Mass121/laya-typed-decisions-v2` at
`http://127.0.0.1:5056/decide`. Use the existing isolated V2 environment and
checkpoint; see `laya_v2_service/README.md` for provisioning details. The old
`laya_service/server.js` ONNX service on 5055 is a separate historical service
and does not satisfy the V2 client identity check. Do not run both V2 and the
old opt-in switchable service on 5056.

### Terminal 3 - Ollama (port 11434)

```powershell
ollama serve
```

Pull the model only if it is not already available locally. FastAPI is
configured to use `llama3.2:latest` at `http://localhost:11434/api/chat`.

### Terminal 4 - React frontend (port 8080)

```powershell
cd ecom-muse-main\frontend
npm.cmd ci
npm.cmd run dev -- --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080`. The frontend API base URL is configured in
`frontend/.env` and should point to `http://localhost:8000`.
