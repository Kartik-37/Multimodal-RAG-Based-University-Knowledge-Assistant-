# PostgreSQL 16 + pgvector Setup Guide on Windows

This guide explains how to set up, configure, and maintain the authoritative local **PostgreSQL 16 + pgvector** database environment for the **Multimodal RAG-Based University Knowledge Assistant** on Windows.

---

## 1. Overview & Architecture

* **Database Engine**: PostgreSQL 16 (64-bit).
* **Vector Extension**: `pgvector` v0.8.6 (supports `vector(1024)` matching the `qwen3-embedding:0.6b` model).
* **Application Database**: `rag_assistant_db` (owned by dedicated role `rag_app_user`).
* **Test Database**: `rag_assistant_test_db` (isolated real PostgreSQL database for automated testing).
* **Python Driver**: `psycopg 3` (`psycopg[binary]`) via SQLAlchemy 2.x synchronous engine.
* **Migration Manager**: Alembic.

---

## 2. PostgreSQL 16 Binary Setup

PostgreSQL 16 is installed in a dedicated directory outside the git repository (e.g., `D:\Kartik\pgsql`):

1. **Download PostgreSQL 16 Binaries**:
   ```powershell
   New-Item -ItemType Directory -Path "D:\Kartik\pgsql_temp" -Force
   curl.exe -L "https://get.enterprisedb.com/postgresql/postgresql-16.15-3-windows-x64-binaries.zip" -o "D:\Kartik\pgsql_temp\postgresql.zip"
   ```

2. **Extract Binaries**:
   ```powershell
   Expand-Archive -Path "D:\Kartik\pgsql_temp\postgresql.zip" -DestinationPath "D:\Kartik\pgsql" -Force
   ```
   *The binaries will be located at `D:\Kartik\pgsql\pgsql\bin\`.*

---

## 3. pgvector Extension Installation

The server-side extension binaries must be registered into PostgreSQL's library and extension paths:

* **Source Repository**: [`andreiramani/pgvector_pgsql_windows`](https://github.com/andreiramani/pgvector_pgsql_windows)
* **Release Version**: `0.8.6_16` (pgvector v0.8.6 compiled for PostgreSQL 16 x64)
* **Direct Asset URL**: `https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/0.8.6_16/vector.v0.8.6-pg16.zip`
* **Target PostgreSQL**: PostgreSQL 16.15 (x64)

1. **Download Precompiled pgvector**:
   ```powershell
   curl.exe -L "https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/0.8.6_16/vector.v0.8.6-pg16.zip" -o "D:\Kartik\pgsql_temp\vector.zip"
   Expand-Archive -Path "D:\Kartik\pgsql_temp\vector.zip" -DestinationPath "D:\Kartik\pgsql_temp\vector_extracted" -Force
   ```

2. **Copy Extension Files to PostgreSQL**:
   ```powershell
   # Copy dynamic link library (.dll)
   Copy-Item -Path "D:\Kartik\pgsql_temp\vector_extracted\lib\vector.dll" -Destination "D:\Kartik\pgsql\pgsql\lib\" -Force

   # Copy control and migration SQL scripts
   Copy-Item -Path "D:\Kartik\pgsql_temp\vector_extracted\share\extension\*" -Destination "D:\Kartik\pgsql\pgsql\share\extension\" -Force

   # Clean up temporary archive
   Remove-Item -Path "D:\Kartik\pgsql_temp" -Recurse -Force
   ```

3. **Verify Files in Place**:
   ```powershell
   Test-Path "D:\Kartik\pgsql\pgsql\lib\vector.dll"                       # Returns True
   Test-Path "D:\Kartik\pgsql\pgsql\share\extension\vector.control"        # Returns True
   ```

---

## 4. Initialize Database Cluster

Initialize the data directory `D:\Kartik\pgsql\data` with UTF-8 encoding:

```powershell
& "D:\Kartik\pgsql\pgsql\bin\initdb.exe" -D "D:\Kartik\pgsql\data" -U postgres -E UTF8 -A scram-sha-256
```

---

## 5. Running PostgreSQL: Daemon vs Windows Service

### Option A: Background Daemon (Non-Elevated / Development Mode)
Standard user shells on Windows run at *Medium Mandatory Level* (`BUILTIN\Administrators` used for deny-only). The server can run reliably in the background without needing administrator privileges:

```powershell
# Start daemon:
& "D:\Kartik\pgsql\pgsql\bin\pg_ctl.exe" start -D "D:\Kartik\pgsql\data" -l "D:\Kartik\pgsql\logfile.log"

# Check status:
& "D:\Kartik\pgsql\pgsql\bin\pg_ctl.exe" status -D "D:\Kartik\pgsql\data"

# Stop daemon:
& "D:\Kartik\pgsql\pgsql\bin\pg_ctl.exe" stop -D "D:\Kartik\pgsql\data"
```

### Option B: Windows Service (Requires Administrator PowerShell)
Registering a native Windows service with the Windows Service Control Manager (`OpenSCManager`) requires *High Mandatory Level* (Administrator). Open an **Administrator PowerShell** window and run:

```powershell
# 1. Stop any running background process
& "D:\Kartik\pgsql\pgsql\bin\pg_ctl.exe" stop -D "D:\Kartik\pgsql\data"

# 2. Register service with automatic startup (-S auto)
& "D:\Kartik\pgsql\pgsql\bin\pg_ctl.exe" register -N "postgresql-16" -D "D:\Kartik\pgsql\data" -S auto

# 3. Start the Windows Service
Start-Service -Name "postgresql-16"

# 4. Verify Service Status and Startup Type
Get-Service -Name "postgresql-16" | Select-Object Name, Status, StartType
```
*(Expected status: `Running`, StartType: `Automatic`)*


---

## 6. Creating Roles and Databases

Run the following SQL commands using `psql.exe` to create the application role and databases following least-privilege principles:

```powershell
$psql = "D:\Kartik\pgsql\pgsql\bin\psql.exe"

# 1. Create dedicated application role (replace YOUR_PASSWORD with a strong secret)
& $psql -U postgres -h 127.0.0.1 -p 5432 -c "CREATE ROLE rag_app_user WITH LOGIN PASSWORD 'YOUR_PASSWORD' NOSUPERUSER NOCREATEDB NOCREATEROLE;"

# 2. Create production and test databases owned by rag_app_user
& $psql -U postgres -h 127.0.0.1 -p 5432 -c "CREATE DATABASE rag_assistant_db OWNER rag_app_user;"
& $psql -U postgres -h 127.0.0.1 -p 5432 -c "CREATE DATABASE rag_assistant_test_db OWNER rag_app_user;"

# 3. Enable pgvector on both databases
& $psql -U postgres -h 127.0.0.1 -p 5432 -d rag_assistant_db -c "CREATE EXTENSION IF NOT EXISTS vector; GRANT ALL ON SCHEMA public TO rag_app_user;"
& $psql -U postgres -h 127.0.0.1 -p 5432 -d rag_assistant_test_db -c "CREATE EXTENSION IF NOT EXISTS vector; GRANT ALL ON SCHEMA public TO rag_app_user;"
```

---

## 7. Verifying pgvector and vector(1024)

Verify the extension version and 1024-dimension vector operations:

```powershell
& $psql -U rag_app_user -h 127.0.0.1 -p 5432 -d rag_assistant_db -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```
*Expected output: `vector | 0.8.6`.*

Test vector dimension verification:
```powershell
& $psql -U rag_app_user -h 127.0.0.1 -p 5432 -d rag_assistant_db -c "
CREATE TEMP TABLE t (id serial, v vector(1024));
INSERT INTO t (v) VALUES (array_fill(0.1::real, ARRAY[1024])::vector);
SELECT id, vector_dims(v) FROM t;
"
```
*Expected output: `1024`.*

---

## 8. Application Environment Configuration (`.env`)

Configure your local `.env` file (which is excluded from git):

```env
# Application Settings
APP_NAME="BCA RAG Assistant"
APP_ENV="development"
DEBUG=true
API_V1_STR="/api/v1"

# Security
SECRET_KEY="your-secure-random-secret-key"
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM="HS256"

# Database URLs (PostgreSQL + pgvector via psycopg)
DATABASE_URL="postgresql+psycopg://rag_app_user:YOUR_PASSWORD@127.0.0.1:5432/rag_assistant_db"
TEST_DATABASE_URL="postgresql+psycopg://rag_app_user:YOUR_PASSWORD@127.0.0.1:5432/rag_assistant_test_db"

# Storage & Models
STORAGE_DIR="./storage"
OLLAMA_BASE_URL="http://127.0.0.1:11434"
OLLAMA_LLM_MODEL="qwen3:4b"
OLLAMA_EMBED_MODEL="qwen3-embedding:0.6b"
EMBEDDING_DIM=1024
RERANKER_MODEL="cross-encoder/ms-marco-MiniLM-L-6-v2"
```

---

## 9. Running Alembic Database Migrations

Apply migration scripts to create extension and schema:

```powershell
# In project root with active .venv:
alembic upgrade head

# Check current migration revision:
alembic current
```

---

## 10. Verification Tests & Readiness Probes

### Run Integration Tests
```powershell
pytest backend/tests/integration/test_database.py
```

### Check Probes
Start the FastAPI server:
```powershell
uvicorn backend.app.main:app --reload --port 8000
```

1. **Liveness Probe** (`http://127.0.0.1:8000/health`):
   * Returns HTTP 200 `{"status": "healthy", ...}`
2. **Readiness Probe** (`http://127.0.0.1:8000/ready`):
   * If PostgreSQL is running: Returns HTTP 200 `{"status": "ready", "checks": {"database": "ok", ...}}`
   * If PostgreSQL is stopped: Returns HTTP 503 `{"status": "not_ready", "checks": {"database": "unavailable", ...}}` without leaking connection secrets.

---

## 11. Troubleshooting

| Problem | Cause | Resolution |
| :--- | :--- | :--- |
| `could not connect to server: Connection refused` | PostgreSQL server process is not running. | Run `pg_ctl start -D "D:\Kartik\pgsql\data" -l "D:\Kartik\pgsql\logfile.log"`. |
| `extension "vector" is not available` | `vector.dll` or `vector.control` is missing. | Re-copy `vector.dll` into `pgsql/lib/` and `vector.control` into `pgsql/share/extension/`. |
| `password authentication failed for user "rag_app_user"` | Incorrect password in `.env` or SCRAM mismatch. | Verify the password in `.env` matches the password set in PostgreSQL. |
| `port 5432 is already in use` | Another PostgreSQL or service is bound to port 5432. | Check `netstat -ano \| findstr 5432` or configure `port = 5433` in `postgresql.conf` and update `DATABASE_URL`. |
