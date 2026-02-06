from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        query_components = parse_qs(urlparse(self.path).query)
        video_input = query_components.get('video_id', [None])[0]
        
        if not video_input:
            self.wfile.write(json.dumps({
                'error': 'Parámetro video_id requerido',
                'example': '/api/transcript?video_id=dQw4w9WgXcQ'
            }).encode())
            return
        
        # Extraer video_id si viene URL completa
        video_id = self.extract_video_id(video_input)
        
        try:
            # Listar todos los transcripts disponibles
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Intentar obtener transcript en orden de preferencia
            try:
                # Primero intentar manual en español
                transcript = transcript_list.find_manually_created_transcript(['es', 'es-419'])
            except:
                try:
                    # Luego manual en inglés
                    transcript = transcript_list.find_manually_created_transcript(['en'])
                except:
                    try:
                        # Luego auto-generado en español
                        transcript = transcript_list.find_generated_transcript(['es', 'es-419'])
                    except:
                        # Finalmente auto-generado en inglés
                        transcript = transcript_list.find_generated_transcript(['en'])
            
            # Obtener el texto
            transcript_data = transcript.fetch()
            texto_completo = ' '.join([entry['text'] for entry in transcript_data])
            
            response = {
                'success': True,
                'video_id': video_id,
                'transcript': texto_completo,
                'language': transcript.language,
                'is_generated': transcript.is_generated,
                'length': len(texto_completo)
            }
            
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            
        except TranscriptsDisabled:
            self.wfile.write(json.dumps({
                'success': False,
                'error': 'Este video no tiene subtítulos habilitados',
                'video_id': video_id,
                'suggestion': 'Verifica que el video tenga subtítulos automáticos o manuales'
            }).encode())
            
        except NoTranscriptFound:
            self.wfile.write(json.dumps({
                'success': False,
                'error': 'No se encontraron transcripts en ningún idioma',
                'video_id': video_id
            }).encode())
            
        except Exception as e:
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e),
                'video_id': video_id
            }).encode())
    
    def extract_video_id(self, url_or_id):
        """Extrae video_id de URL o devuelve el ID directamente"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        return url_or_id