# YT Transcript API 🎙️

API para transcribir videos de YouTube, **incluso aquellos sin subtítulos**.  
Usa subtítulos existentes cuando están disponibles y [Whisper](https://github.com/openai/whisper) como fallback.

## Características

- ✅ Obtiene subtítulos manuales o auto-generados (rápido, sin descargar audio)
- 🎙️ Transcripción con Whisper cuando no hay subtítulos (gratuito, local)
- 🌐 Soporte multiidioma (español, inglés, y más)
- 📖 Documentación Swagger automática en `/docs`
- 🐳 Despliegue con Docker en un comando
- 🔗 Compatible con n8n, Make, Zapier, etc.

## Inicio rápido

### Con Docker (recomendado)

```bash
# Construir y ejecutar
docker compose up -d --build

# La API estará disponible en http://localhost:8000
```

### Sin Docker (desarrollo)

```bash
# Instalar dependencias (requiere Python 3.10+ y ffmpeg)
pip install -r requirements.txt

# Ejecutar
uvicorn main:app --reload --port 8000
```

## Uso

### Endpoint principal

```
GET /api/transcript?video_id=VIDEO_ID
```

### Parámetros

| Parámetro      | Tipo   | Default | Descripción                                    |
|----------------|--------|---------|------------------------------------------------|
| `video_id`     | string | —       | ID del video o URL completa **(requerido)**     |
| `lang`         | string | `es`    | Idioma preferido para subtítulos               |
| `force_whisper`| bool   | `false` | Forzar transcripción con Whisper               |

### Ejemplos

```bash
# Con ID del video
curl "http://localhost:8000/api/transcript?video_id=dQw4w9WgXcQ"

# Con URL completa
curl "http://localhost:8000/api/transcript?video_id=https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Forzar Whisper (ignorar subtítulos existentes)
curl "http://localhost:8000/api/transcript?video_id=dQw4w9WgXcQ&force_whisper=true"

# En inglés
curl "http://localhost:8000/api/transcript?video_id=dQw4w9WgXcQ&lang=en"
```

### Respuesta exitosa

```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "transcript": "Texto completo de la transcripción...",
  "language": "Spanish",
  "language_code": "es",
  "is_generated": true,
  "method": "subtitles",
  "length": 1234
}
```

## Configuración con n8n

1. Agrega un nodo **HTTP Request**
2. Configura:
   - **Method:** GET
   - **URL:** `http://TU_SERVIDOR:8000/api/transcript`
   - **Query Parameters:** `video_id` = `{{ $json.videoUrl }}`
3. El campo `transcript` de la respuesta contiene el texto completo

## Modelos Whisper disponibles

| Modelo    | Tamaño | RAM   | Velocidad | Precisión |
|-----------|--------|-------|-----------|-----------|
| `tiny`    | ~75 MB | ~1 GB | ⚡⚡⚡⚡⚡ | ⭐⭐       |
| `base`    | ~150 MB| ~1 GB | ⚡⚡⚡⚡   | ⭐⭐⭐     |
| `small`   | ~500 MB| ~2 GB | ⚡⚡⚡     | ⭐⭐⭐⭐   |
| `medium`  | ~1.5 GB| ~5 GB | ⚡⚡       | ⭐⭐⭐⭐⭐ |
| `large-v3`| ~3 GB  | ~10 GB| ⚡         | ⭐⭐⭐⭐⭐ |

Cambia el modelo en `docker-compose.yml` o con la variable de entorno `WHISPER_MODEL`.

## Endpoints

| Ruta               | Método | Descripción                          |
|--------------------|--------|--------------------------------------|
| `/`                | GET    | Info del servicio                    |
| `/api/transcript`  | GET    | Obtener transcripción                |
| `/api/health`      | GET    | Health check                         |
| `/docs`            | GET    | Documentación Swagger interactiva    |
