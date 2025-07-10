from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Korean Language Problem Extraction and Classification Service"}

# Add endpoints for extraction and classification
