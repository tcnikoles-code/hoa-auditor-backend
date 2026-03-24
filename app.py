import os
import anthropic
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
print(f"API KEY LOADED: {os.environ.get('ANTHROPIC_API_KEY', 'NOT FOUND')[:20]}...")
SYSTEM_PROMPT = """You are an expert Colorado transaction coordinator auditing HOA documents for compliance with Section 7.3 of the Colorado Contract to Buy and Sell Real Estate.

The required Association Documents under Section 7.3 are:

7.3.1 GOVERNING DOCUMENTS (required):
- All Association declarations
- Articles of incorporation
- Bylaws
- Articles of organization
- Operating agreements
- Rules and regulations
- Party wall agreements (if applicable)
- Association's responsible governance policies (§38-33.3-209.5)

7.3.2 MINUTES (required):
- Minutes of the most recent annual owners'/members' meeting
- Minutes of any executive board or managers' meetings (most current Annual Disclosure + any subsequent)
- If none exist: most recent minutes available

7.3.3 ASSOCIATION INSURANCE DOCUMENTS (required):
- List of all Association insurance policies from last Annual Disclosure
- Must include: property, general liability, director & officer professional liability, fidelity policies
- Each policy must show: company name, policy limits, deductibles, additional named insureds, expiration dates

7.3.4 ASSESSMENT LIST (required):
- List by unit type of all assessments (regular and special) from last Annual Disclosure

7.3.5 FINANCIAL DOCUMENTS (required):
- Operating budget for current fiscal year
- Most recent annual financial statements (including reserve amounts)
- Most recent financial audit or review results
- Fee schedule for closing-related charges (status letter fee, rush fees, record change fee, document access fees)
- List of assessments/reserves/working capital due at closing
- Reserve study (if one exists)

7.3.6 CONSTRUCTION DEFECT DOCUMENTS (required if applicable):
- Any written notice of construction defect action within past 6 months
- Result of Association approval/disapproval
- If no construction defect action exists, note that none is required

Your job:
1. Review the uploaded documents and identify which required items ARE present
2. Identify clearly which required items are MISSING or INCOMPLETE
3. Note any items that are present but may be outdated or incomplete
4. Generate a clean audit summary with ✅ PRESENT, ❌ MISSING, or ⚠️ INCOMPLETE/UNCLEAR status for each section
5. Then generate a professional, concise follow-up email to request missing documents - written in a friendly but clear TC voice, not legal language. Sign it from Nikole at Broker Relief Transaction Management, nikole@brokerrelieftm.com, (970) 599-1172.

Format your response in two clearly labeled sections:
--- AUDIT SUMMARY ---
[your audit findings]

--- FOLLOW-UP EMAIL ---
[the email, or write NONE NEEDED if all documents are present and complete]"""

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/audit', methods=['POST', 'OPTIONS'])
def audit():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response

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
                content_parts.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": file_data
                    }
                })
            elif file_type.startswith('image/'):
                content_parts.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file_type,
                        "data": file_data
                    }
                })

        context_note = f"Property: {address}\nTransaction side: {side}"
        if context:
            context_note += f"\nAdditional context: {context}"
        context_note += "\n\nPlease audit these HOA documents against the Colorado Contract Section 7.3 requirements."

        content_parts.append({"type": "text", "text": context_note})

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content_parts}]
        )

        full_text = "".join([block.text for block in response.content if hasattr(block, 'text')])

        return jsonify({"result": full_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
