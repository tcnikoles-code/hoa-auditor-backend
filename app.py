import os
import anthropic
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an expert Colorado transaction coordinator auditing HOA documents for compliance with Section 7.3 of the Colorado Contract to Buy and Sell Real Estate.

7.3.1 GOVERNING DOCUMENTS: declarations, articles of incorporation, bylaws, operating agreements, rules and regulations, party wall agreements, responsible governance policies
7.3.2 MINUTES: most recent annual owners meeting minutes, executive board meeting minutes
7.3.3 INSURANCE: all policies with company names, limits, deductibles, named insureds, expiration dates
7.3.4 ASSESSMENT LIST: by unit type, regular and special assessments
7.3.5 FINANCIAL DOCUMENTS: current budget, financial statements, audit/review, closing fee schedule, amounts due at closing, reserve study
7.3.6 CONSTRUCTION DEFECT: any notices within past 6 months

Review the documents and output:
--- AUDIT SUMMARY ---
Each section with status: PRESENT, MISSING, or INCOMPLETE

--- FOLLOW-UP EMAIL ---
Professional email requesting missing items, signed from Nikole at Broker Relief Transaction Management, nikole@brokerrelieftm.com, (970) 599-1172. Write NONE NEEDED if everything is present."""

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/audit', methods=['POST', 'OPTIONS'])
def audit():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})
    try:
        data = request.json
        address = data.get('address', 'Unknown property')
        side = data.get('side', 'buyer')
        context = data.get('context', '')
        files = data.get('files', [])

        content_parts = []
        for f in files:
            file_data = f.get('data')
            file_type = f.get('type')
            if file_type == 'application/pdf':
                content_parts.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": file_data}})
            elif file_type.startswith('image/'):
                content_parts.append({"type": "image", "source": {"type": "base64", "media_type": file_type, "data": file_data}})

        note = f"Property: {address}\nSide: {side}"
        if context:
            note += f"\nContext: {context}"
        note += "\n\nAudit these HOA documents against Colorado Contract Section 7.3."
        content_parts.append({"type": "text", "text": note})

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content_parts}]
        )
        result = "".join([b.text for b in response.content if hasattr(b, 'text')])
        return jsonify({"result": result})

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
