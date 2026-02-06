from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import yt_dlp
from faster_whisper import WhisperModel
import tempfile
import os
import re
import logging

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")   # tiny | base | small | medium | large-v3
DEVICE = os.getenv("DEVICE", "cpu")                       # cpu | cuda
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "auto")          # auto | int8 | float16 | float32
MAX_DURATION = int(os.getenv("MAX_DURATION", "3600"))      # máx duración en segundos (default 1h)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yt-transcript-api")

whisper_model: WhisperModel | None = None


# ---------------------------------------------------------------------------
# Lifespan – carga el modelo Whisper al iniciar
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global whisper_model
    logger.info(f"⏳ Cargando modelo Whisper '{WHISPER_MODEL_SIZE}' en {DEVICE} ({COMPUTE_TYPE})…")
    whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    logger.info("✅ Modelo Whisper cargado correctamente")
    yield
    logger.info("🛑 Apagando servicio")


# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="YT Transcript API",
    description="API para transcribir videos de YouTube, incluso sin subtítulos. "
                "Usa subtítulos existentes cuando están disponibles y Whisper como fallback.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def extract_video_id(url_or_id: str) -> str:
    """Extrae el video_id de una URL de YouTube o devuelve el ID tal cual."""
    patterns = [
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:v=)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})',
        r'^([0-9A-Za-z_-]{11})$',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def get_subtitles(video_id: str, lang: str = "es") -> dict | None:
    """Intenta obtener subtítulos existentes del video (rápido, sin descargar audio)."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Códigos de idioma a probar
        lang_codes = [lang]
        if lang == "es":
            lang_codes = ["es", "es-419", "es-ES"]

        # Orden de preferencia: manual → generado, idioma pedido → inglés
        search_order = [
            (transcript_list.find_manually_created_transcript, lang_codes),
            (transcript_list.find_manually_created_transcript, ["en"]),
            (transcript_list.find_generated_transcript, lang_codes),
            (transcript_list.find_generated_transcript, ["en"]),
        ]

        for find_fn, codes in search_order:
            try:
                transcript = find_fn(codes)
                data = transcript.fetch()
                text = " ".join(entry["text"] for entry in data)
                return {
                    "transcript": text,
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                    "method": "subtitles",
                }
            except Exception:
                continue

    except (TranscriptsDisabled, NoTranscriptFound):
        logger.info(f"No se encontraron subtítulos para {video_id}")
    except Exception as e:
        logger.warning(f"Error buscando subtítulos: {e}")

    return None


def transcribe_with_whisper(video_id: str, lang: str | None = None) -> dict:
    """Descarga el audio del video y lo transcribe con Whisper."""
    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "audio")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "match_filter": yt_dlp.utils.match_filter_func(
                f"duration <= {MAX_DURATION}"
            ),
        }

        logger.info(f"⬇️  Descargando audio de {video_id}…")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise ValueError(
                    f"No se pudo obtener información del video {video_id}. "
                    f"Puede que exceda la duración máxima ({MAX_DURATION}s)."
                )
            video_title = info.get("title", "")

        # Buscar archivo de audio generado
        audio_file = output_path + ".mp3"
        if not os.path.exists(audio_file):
            for f in os.listdir(tmpdir):
                audio_file = os.path.join(tmpdir, f)
                break

        if not os.path.exists(audio_file):
            raise FileNotFoundError("No se pudo descargar el audio del video")

        # Transcribir
        logger.info(f"🎙️  Transcribiendo con Whisper ({WHISPER_MODEL_SIZE})…")
        segments, info = whisper_model.transcribe(
            audio_file,
            language=lang if lang and lang != "auto" else None,
            beam_size=5,
            vad_filter=True,           # Filtra silencios para mayor velocidad
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
        )

        # Recopilar texto
        full_text = " ".join(segment.text.strip() for segment in segments)

        return {
            "transcript": full_text,
            "language": info.language,
            "language_code": info.language,
            "is_generated": True,
            "method": "whisper",
            "whisper_model": WHISPER_MODEL_SIZE,
            "video_title": video_title,
        }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    """Información del servicio y ejemplos de uso."""
    return {
        "service": "YT Transcript API",
        "version": "2.0.0",
        "endpoints": {
            "/api/transcript": {
                "method": "GET",
                "description": "Obtiene la transcripción de un video de YouTube",
                "parameters": {
                    "video_id": "(requerido) ID del video o URL completa",
                    "lang": "(opcional) Idioma preferido — default: es",
                    "force_whisper": "(opcional) Forzar transcripción con Whisper — default: false",
                },
                "example": "/api/transcript?video_id=dQw4w9WgXcQ",
            }
        },
        "docs": "/docs",
    }


@app.get("/api/transcript")
async def get_transcript(
    video_id: str = Query(
        ...,
        description="ID del video de YouTube o URL completa",
        examples=["dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    ),
    lang: str = Query(
        "es",
        description="Idioma preferido para los subtítulos (es, en, fr, pt, etc.)",
    ),
    force_whisper: bool = Query(
        False,
        description="Forzar transcripción con Whisper ignorando subtítulos existentes",
    ),
):
    """
    Transcribe un video de YouTube.

    **Flujo:**
    1. Intenta obtener subtítulos existentes (manuales o automáticos).
    2. Si no hay subtítulos (o `force_whisper=true`), descarga el audio y lo
       transcribe localmente con Whisper.

    **Ideal para n8n:** usar el nodo HTTP Request con método GET.
    """
    vid = extract_video_id(video_id)

    # 1️⃣ Intentar subtítulos existentes
    if not force_whisper:
        result = get_subtitles(vid, lang)
        if result:
            logger.info(f"✅ Subtítulos encontrados para {vid} ({result['method']})")
            return {
                "success": True,
                "video_id": vid,
                **result,
                "length": len(result["transcript"]),
            }

    # 2️⃣ Fallback: Whisper
    try:
        result = transcribe_with_whisper(vid, lang if lang != "auto" else None)
        logger.info(f"✅ Transcripción Whisper completada para {vid}")
        return {
            "success": True,
            "video_id": vid,
            **result,
            "length": len(result["transcript"]),
        }
    except Exception as e:
        logger.error(f"❌ Error transcribiendo {vid}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "video_id": vid,
                "suggestion": "Verifica que el video exista y sea público",
            },
        )


@app.get("/api/health")
async def health():
    """Health check para monitoreo."""
    return {
        "status": "ok",
        "whisper_model": WHISPER_MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
    }
