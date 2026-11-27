"""Run the HRA backend using backend/.env (no overrides)."""
import os, sys
os.chdir(r"C:/Users/khang/Downloads/Vinuni-IT-CV/VinIT_HRApp/backend")
sys.path.insert(0, os.getcwd())
# Tesseract (F2.06 image OCR) for this process only; the Windows PATH is unchanged.
os.environ["PATH"] = r"C:\Program Files\Tesseract-OCR" + os.pathsep + os.environ.get("PATH", "")
# F2.07 retention test: show the purge OTP in the response (no SMTP here). Dev only;
# config refuses it outside APP_ENV=development/testing. backend/.env is unchanged.
os.environ["RETENTION_OTP_DEV_ECHO"] = "true"
# P3-3 public /apply portal for local testing only (malware scan "off" is accepted in development).
os.environ["PUBLIC_INTAKE_ENABLED"] = "true"
import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
