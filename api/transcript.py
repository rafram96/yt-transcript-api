from youtube_transcript_api import YouTubeTranscriptApi
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Habilitar CORS
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Parsear query params
        query_components = parse_qs(urlparse(self.path).query)
        video_id = query_components.get('video_id', [None])[0]
        
        if not video_id:
            self.wfile.write(json.dumps({
                'error': 'Parámetro video_id requerido',
                'example': '/api/transcript?video_id=dQw4w9WgXcQ'
            }).encode())
            return
        
        try:
            # Intentar varios idiomas
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id, 
                languages=['es', 'en', 'es-419', 'en-US']
            )
            
            # Unir todo el texto
            texto_completo = ' '.join([entry['text'] for entry in transcript])
            
            response = {
                'success': True,
                'video_id': video_id,
                'transcript': texto_completo,
                'length': len(texto_completo)
            }
            
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            
        except Exception as e:
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e),
                'video_id': video_id
            }).encode())