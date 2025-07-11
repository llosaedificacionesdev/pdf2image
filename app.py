from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from pdf2image import convert_from_path
import tempfile, os

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "✅ PDF to JPG API is running."}

@app.post("/convert")
async def convert(pdf_file: UploadFile = File(...)):
    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sólo archivos PDF.")
    # Usa un temp dir para input y salida
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, pdf_file.filename)
        contents = await pdf_file.read()
        with open(in_path, "wb") as f:
            f.write(contents)
        # Convierte todas las páginas a JPEG en tmpdir
        images = convert_from_path(
            in_path,
            dpi=200,
            output_folder=tmpdir,
            fmt="jpeg",
            thread_count=1
        )
        # Devuelve la primera página convertida
        out_path = os.path.join(tmpdir, "page1.jpg")
        images[0].save(out_path, "JPEG")
        return FileResponse(out_path, media_type="image/jpeg")
