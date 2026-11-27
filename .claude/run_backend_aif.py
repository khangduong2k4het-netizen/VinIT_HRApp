"""Run the AI_features (ai_f) build of HRA: folder VinIT_HRApp_aif, port 8001,
database hra_aif (from VinIT_HRApp_aif/backend/.env). Local only; not committed."""
import os
import sys

os.chdir(r"C:/Users/khang/Downloads/Vinuni-IT-CV/VinIT_HRApp_aif/backend")
sys.path.insert(0, os.getcwd())
# Tesseract stays available for the HRA reader used as fallback.
os.environ["PATH"] = r"C:\Program Files\Tesseract-OCR" + os.pathsep + os.environ.get("PATH", "")
os.environ["RETENTION_OTP_DEV_ECHO"] = "true"
os.environ["PUBLIC_INTAKE_ENABLED"] = "true"
import uvicorn  # noqa: E402

uvicorn.run("app.main:app", host="127.0.0.1", port=8001)
