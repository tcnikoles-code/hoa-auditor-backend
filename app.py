import os
import anthropic
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

API_KEY = os.environ.get("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = """You are an expert Colorado transaction coordinator auditing HOA documents for compliance with Section 7.3 of the Colorado Contract to Buy and Sell Real Estate. Review uploaded documents and identify which required items ARE present, MISSING, or INCOMPLETE. Format response in two sections: --- AUDIT SUMMARY --- and --- FOLLOW-UP EMAIL ---. Sign emails from Nikole at Broker Relief Transaction Management, nikole@brokerrelieftm.com, (970) 599-1172."""

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length))
            
            address = body.get('address', 'Unknown')
            side = body.get('side', 'buyer')
            context = body.get('context', '')
            files = body.get('files', [])

            content_parts = []
            for f in files:
                if f['type'] == 'application/pdf':
                    content_parts.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": f['data']}})
                elif f['type'].startswith('image/'):
                    content_parts.append({"type": "image", "source": {"type": "base64", "media_type": f['type'], "data": f['data']}})

            note = f"Property: {address}\nSide: {side}"
            if context:
                note += f"\nContext: {context}"
            note += "\n\nAudit these HOA documents against Colorado Contract Section 7.3."
            content_parts.append({"type": "text", "text": note})

            client = anthropic.Anthropic(api_key=API_KEY)
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content_parts}]
            )
            result = "".join([b.text for b in response.content if hasattr(b, 'text')])

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"result": result}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting server on port {port}")
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
```

Also update `requirements.txt` to just:
```
anthropic
```

And update the start command in Railway to:
```
python app.py
