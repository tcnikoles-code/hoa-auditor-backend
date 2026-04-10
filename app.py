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

FORMATTING RULES - follow these exactly:
- Always use PRESENT, MISSING, or INCOMPLETE with emoji: check mark for present, x for missing, warning for incomplete
- Never use markdown bold (no ** stars **)
- Never use markdown headers
- Keep it plain text with emoji status indicators only
- For the follow-up email: keep it short, friendly, and conversational - no bullet point explanations, just a simple list of what is needed. No legal language. Sound like a real person.

Review the documents and output:

--- AUDIT SUMMARY ---
7.3.1 Governing Documents
[status emoji] [item]: [brief note]
[continue for each item]
Overall status: [emoji]

[repeat for 7.3.2 through 7.3.6]

--- FOLLOW-UP EMAIL ---
[short friendly email listing only what is missing, signed from Nikole at Broker Relief Transaction Management, nikole@brokerrelieftm.com, (970) 599-1172. Write NONE NEEDED if everything is present.]"""

BATCH_PROMPT = """You are an expert Colorado transaction coordinator reviewing a batch of HOA documents.

Identify which Section 7.3 items are present in THIS batch:
7.3.1: declarations, articles of incorporation, bylaws, rules and regulations, party wall agreements, governance policies
7.3.2: annual meeting minutes, board meeting minutes
7.3.3: insurance certificates/policies
7.3.4: assessment schedules
7.3.5: budget, financial statements, audit, fee schedule, reserve study
7.3.6: construction defect notices

List only what you FIND. Be specific. Plain text only, no markdown."""

MERGE_PROMPT = """You are an expert Colorado transaction coordinator. Multiple batches of HOA documents have been reviewed. Combine all findings and produce a final Section 7.3 audit.

FORMATTING RULES:
- Use checkmark emoji for PRESENT, x emoji for MISSING, warning emoji for INCOMPLETE
- No markdown bold, no stars, no headers
- Plain text with emoji only
- Follow-up email: short, friendly, conversational, simple list of missing items only

Output:
--- AUDIT SUMMARY ---
7.3.1 Governing Documents
[status] [item]: [note]
Overall: [status]

[repeat 7.3.2 through 7.3.6]

--- FOLLOW-UP EMAIL ---
[short friendly email, signed from Nikole at Broker Relief Transaction Management, nikole@brokerrelieftm.com, (970) 599-1172. Write NONE NEEDED if complete.]"""

BATCH_SIZE = 5
MAX_SIZE_MB = 8

def size_mb(files):
    return sum(len(f.get('data', '')) * 0.75 for f in files) / (1024 * 1024)

def build_parts(files):
    parts = []
    for f in files:
        t = f.get('type', '')
        d = f.get('data')
        if t == 'application/pdf':
            parts.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": d}})
        elif t.startswith('image/'):
            parts.append({"type": "image", "source": {"type": "base64", "media_type": t, "data": d}})
    return parts

def make_batches(files):
    batches, batch, size = [], [], 0
    for f in files:
        fs = len(f.get('data', '')) * 0.75 / (1024 * 1024)
        if (size + fs > MAX_SIZE_MB or len(batch) >= BATCH_SIZE) and batch:
            batches.append(batch)
            batch, size = [f], fs
        else:
            batch.append(f)
            size += fs
    if batch:
        batches.append(batch)
    return batches

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

        total = size_mb(files)
        print(f"Files: {len(files)}, Size: {total:.1f}MB")

        note = f"Property: {address}\nSide: {side}"
        if context:
            note += f"\nContext: {context}"

        if total <= MAX_SIZE_MB and len(files) <= BATCH_SIZE:
            parts = build_parts(files)
            parts.append({"type": "text", "text": note + "\n\nAudit these HOA documents against Colorado Contract Section 7.3."})
            resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=2000, system=SYSTEM_PROMPT, messages=[{"role": "user", "content": parts}])
            return jsonify({"result": "".join([b.text for b in resp.content if hasattr(b, 'text')])})

        else:
            batches = make_batches(files)
            print(f"Batch mode: {len(batches)} batches")
            findings = []
            for i, batch in enumerate(batches):
                parts = build_parts(batch)
                parts.append({"type": "text", "text": f"Batch {i+1} of {len(batches)} for {address}. What Section 7.3 HOA documents are in this batch?"})
                resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=1000, system=BATCH_PROMPT, messages=[{"role": "user", "content": parts}])
                findings.append(f"BATCH {i+1}:\n" + "".join([b.text for b in resp.content if hasattr(b, 'text')]))

            combined = "\n\n".join(findings)
            resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=2000, system=MERGE_PROMPT,
                messages=[{"role": "user", "content": f"{note}\n\nFindings from all batches:\n\n{combined}\n\nProduce the final Section 7.3 audit."}])
            return jsonify({"result": "".join([b.text for b in resp.content if hasattr(b, 'text')])})

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
