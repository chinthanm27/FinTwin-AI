# Setup guide (Windows 10/11 + PowerShell)

This guide assumes nothing is installed yet. Every command is run in **PowerShell**.

## 1. Install Python 3.11.9

1. Download the Windows installer (64-bit) for **Python 3.11.9** from python.org.
2. On the first installer screen tick **Add python.exe to PATH**, then click **Install Now**.
3. Close and reopen PowerShell, then check:

```powershell
py --list
py -3.11 --version
```

## 2. Put the project in place

Unzip the project so that this file is at `D:\FinTwin_AI\docs\setup.md`, then:

```powershell
D:
Set-Location D:\FinTwin_AI
Get-ChildItem
```

You should see `app`, `docs`, `tests`, `requirements.txt` and so on.

## 3. Create and activate the virtual environment

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell says running scripts is disabled, run this once and activate again:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

Your prompt now starts with `(venv)`. Confirm:

```powershell
python --version
```

## 4. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Configure `.env`

```powershell
Copy-Item .env.example .env
```

Generate a session secret (pure PowerShell):

```powershell
$bytes = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
[Convert]::ToBase64String($bytes)
```

Open `.env` (e.g. `notepad .env`) and paste the printed value after `STORAGE_SECRET=`.

## 6. Choose a database

**Option A: MongoDB (persistent, recommended)**

1. Install **MongoDB Community Server** (MSI) and keep "Install MongoDB as a Service" ticked.
2. Make sure it's running:

```powershell
Get-Service MongoDB
net start MongoDB
```

3. Keep `MONGO_URI=mongodb://localhost:27017` in `.env`.

**Option B: Demo mode (no installation)**

Set `MONGO_URI=mongomock://localhost` in `.env`. Everything works, but data is kept in memory and disappears when the app stops.

## 7. Run

```powershell
python -m app.main
```

You should see `NiceGUI ready to go on http://127.0.0.1:8080`. Open that address, create an account, and click **Load demo data**.

Stop the app with `Ctrl + C`.

## 8. Optional

Enable the Gemini-powered Copilot by adding your key to `.env`:

```text
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
```

Restart the app. Without a key, the Copilot uses the offline twin engine.

Retrain the spending model and regenerate the synthetic datasets:

```powershell
python -m app.ai.train_models
```

Run the tests:

```powershell
pytest
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Unable to connect to MongoDB" on a page | Start MongoDB (`net start MongoDB`) or switch to demo mode. |
| `ModuleNotFoundError: No module named 'app'` | Run commands from `D:\FinTwin_AI`, using `python -m app.main`. |
| Port 8080 already in use | Change `APP_PORT` in `.env`. |
| Logged out after restarting | Set a fixed `STORAGE_SECRET` in `.env`. |
| Technical details | See `logs\fintwin.log`. |
