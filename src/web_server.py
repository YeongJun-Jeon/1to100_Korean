import os
import sys
import uuid
import subprocess
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, PlainTextResponse
from src.config import Config

app = FastAPI()

@app.post("/shuffle")
async def shuffle_pdf(file: UploadFile = File(...)):
    config = Config()
    raw_dir = os.path.join(config.DATA_DIR, "raw_0725")
    os.makedirs(raw_dir, exist_ok=True)
    for name in os.listdir(raw_dir):
        if name.lower().endswith(".pdf"):
            os.remove(os.path.join(raw_dir, name))
    input_pdf = os.path.join(raw_dir, f"upload_{uuid.uuid4().hex}.pdf")
    with open(input_pdf, "wb") as f:
        f.write(await file.read())
    try:
        subprocess.run([sys.executable, "-m", "src.main"], check=True)
    except subprocess.CalledProcessError as e:
        return PlainTextResponse(f"처리 중 오류가 발생했습니다: {e}", status_code=500)
    output_pdf = config.RECOMBINED_PDF_OUTPUT_PATH
    return FileResponse(path=output_pdf, media_type="application/pdf", filename=os.path.basename(output_pdf))
