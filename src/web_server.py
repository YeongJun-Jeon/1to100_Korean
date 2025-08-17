import os
import shutil

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse

from src.main import run_pipeline
from src.config import Config


app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    """간단한 업로드 폼을 제공합니다."""
    return (
        "<h3>PDF 셔플 업로드</h3>"
        "<form action='/shuffle' method='post' enctype='multipart/form-data'>"
        "<input type='file' name='file' accept='application/pdf'>"
        "<input type='submit' value='업로드'>"
        "</form>"
    )


@app.post("/shuffle")
async def shuffle_pdf(file: UploadFile = File(...)):
    """업로드된 PDF를 셔플하여 결과 PDF를 반환합니다."""
    config = Config()
    upload_dir = os.path.join(config.PROJECT_ROOT, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    saved_path = os.path.join(upload_dir, file.filename)
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    output_pdf = run_pipeline(saved_path)
    return FileResponse(output_pdf, media_type="application/pdf", filename=os.path.basename(output_pdf))

