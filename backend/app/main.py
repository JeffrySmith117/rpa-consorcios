import logging
import logging.handlers
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.exceptions import AppError
from app.services.consultas import marcar_execucoes_orfas

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def configurar_logs() -> None:
    s = get_settings()
    s.log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    arquivo = logging.handlers.RotatingFileHandler(s.log_dir / "rpa.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    arquivo.setFormatter(fmt)
        # Console do Windows (cp1252) não codifica emojis/setas: substitui em vez de quebrar o log.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    raiz = logging.getLogger()
    raiz.setLevel(s.log_level)
    raiz.handlers[:] = [arquivo, console]
    logging.getLogger("httpx").setLevel(logging.WARNING)
    


@asynccontextmanager
async def lifespan(_: FastAPI):
    configurar_logs()
    init_db()
    with SessionLocal() as db:
        if n := marcar_execucoes_orfas(db):
            logging.getLogger(__name__).warning("%s execução(ões) órfã(s) marcada(s) como erro.", n)
    logging.getLogger(__name__).info("Aplicação iniciada (WhatsApp: %s)", get_settings().whatsapp_provider)
    yield


app = FastAPI(title="RPA Consórcios BCB → WhatsApp", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def tratar_app_error(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"codigo": exc.codigo, "detail": exc.mensagem})


@app.exception_handler(Exception)
async def tratar_erro_inesperado(_: Request, exc: Exception):
    logging.getLogger(__name__).exception("Erro não tratado")
    return JSONResponse(status_code=500, content={"codigo": "ERRO_INTERNO", "detail": "Erro interno. Consulte os logs."})


@app.get("/api/saude")
def saude():
    return {"status": "ok"}


app.include_router(router)

# Em "produção local" o FastAPI também serve o frontend compilado (npm run build),
# então a demonstração roda com um único comando.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):
        return FileResponse(FRONTEND_DIST / "index.html")
