# app.py
import io
import os
import tempfile
import zipfile
from typing import Optional, List

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError
from starlette.middleware.cors import CORSMiddleware

app = FastAPI(title="PDF2Image API", version="1.0")

# CORS (ajusta orígenes si necesitas restringir)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

MAX_FILE_SIZE_MB = 50  # ajusta a tu realidad
ALLOWED_FORMATS = {"png", "jpeg", "jpg"}  # pdf2image: fmt="jpeg" produce .jpg

@app.get("/api/v1/health")
def health():
    return {"status": "ok"}

def _ensure_pdf_file(file: UploadFile) -> None:
    # Chequeo sencillo del magic header %PDF
    # (no es infalible, pero evita content-types engañosos)
    pos = file.file.tell()
    head = file.file.read(5)
    file.file.seek(pos)
    if head != b"%PDF-":
        raise HTTPException(status_code=400, detail="El archivo no parece ser un PDF válido.")

def _size_guard(file: UploadFile):
    # Si el backend está detrás de un proxy que no limita el tamaño, esta rutina
    # hace un read para medir. Para streams grandes, mejor limitar a nivel de proxy.
    pos = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(pos)
    if size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"PDF supera {MAX_FILE_SIZE_MB} MB.")

@app.post("/api/v1/convert/pdf/img")
async def convert_pdf_to_images(
    file: UploadFile = File(..., description="PDF a convertir"),
    dpi: int = Query(200, ge=72, le=600),
    format: str = Query("png", description="png | jpeg | jpg"),
    first_page: Optional[int] = Query(None, ge=1),
    last_page: Optional[int] = Query(None, ge=1),
    timeout: int = Query(300, ge=10, le=1800),
):
    format = format.lower()
    if format == "jpg":
        format = "jpeg"
    if format not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Formato no soportado: {format}")

    _ensure_pdf_file(file)
    _size_guard(file)

    try:
        # Leemos bytes una vez (evita leer todo en RAM con PIL si usamos paths_only + output_folder)
        pdf_bytes = await file.read()

        with tempfile.TemporaryDirectory() as tmpdir:
            # paths_only=True evita cargar PIL Images en memoria → escalable
            paths: List[str] = convert_from_bytes(
                pdf_bytes,
                dpi=dpi,
                output_folder=tmpdir,
                fmt=format,
                first_page=first_page,
                last_page=last_page,
                thread_count=2,
                use_pdftocairo=True,   # suele ser más eficiente
                paths_only=True,
                timeout=timeout,
            )

            if not paths:
                raise HTTPException(status_code=422, detail="No se generaron imágenes.")

            # Creamos ZIP en memoria (para PDFs grandes, cambiar a zip en disco y stream desde archivo)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in sorted(paths):
                    arcname = os.path.basename(p)
                    zf.write(p, arcname=arcname)
            zip_buffer.seek(0)

            filename = (os.path.splitext(file.filename or "output.pdf")[0] or "output") + ".zip"
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )

    except PDFInfoNotInstalledError:
        raise HTTPException(status_code=500, detail="Poppler no está instalado en el servidor.")
    except PDFPageCountError as e:
        raise HTTPException(status_code=400, detail=f"PDF corrupto o ilegible: {e}")
    except PDFSyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Error de sintaxis en el PDF: {e}")
    except Exception as e:
        # Loguea e para diagnóstico; aquí devolvemos mensaje genérico
        raise HTTPException(status_code=500, detail=f"Error al convertir: {str(e)[:200]}")
