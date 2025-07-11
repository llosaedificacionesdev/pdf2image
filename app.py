from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from pdf2image import convert_from_bytes
from io import BytesIO

app = FastAPI()

@app.post("/convert")
async def convert(pdf_file: UploadFile = File(...)):
    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Sólo archivos PDF.")
    contents = await pdf_file.read()
    # Convierte en memoria y devuelve el JPEG
    images = convert_from_bytes(contents, dpi=200)
    buf = BytesIO()
    images[0].save(buf, format="JPEG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")
