from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line
import hashlib

app = Flask(__name__)
# Allow cross-origin requests so the static HTML can POST from localhost or file://
CORS(app, resources={r"/v1/*": {"origins": "*"}})

def sha256_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "API is alive",
        "utc_time": datetime.now(timezone.utc).isoformat()
    })

@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid_json", "detail": "Body must be application/json"}), 400

    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    data = submission.dict()

    if data.get("email"):
        data["email"] = sha256_hash(submission.email)
    if data.get("age") is not None:
        data["age"] = sha256_hash(str(submission.age))

    # 👇 NEW: generate submission_id if missing
    if not data.get("submission_id"):
        raw_email = submission.email
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        unique_str = f"{raw_email}{timestamp}"
        data["submission_id"] = sha256_hash(unique_str)


    record = StoredSurveyRecord(
        **data,
        received_at=datetime.now(timezone.utc),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr or "")
    )
    
    append_json_line(record.dict())
    return jsonify({"status": "ok", "submission_id": data["submission_id"]}), 201

if __name__ == "__main__":
    app.run(port=0, debug=True)
