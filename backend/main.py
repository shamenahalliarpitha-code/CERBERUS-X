from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import uuid, json, re, os

from modules.extractors import extract_file
from modules.analyzer import extract_facts, detect_contradictions

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
UPLOAD_DIR = ROOT / "uploads"
REPORT_DIR = ROOT / "reports"
UPLOAD_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="CERBERUS-X", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

# --- User authentication (SQLite + signed HTTP-only session cookie) ---
import sqlite3, hashlib, hmac, secrets
from fastapi import Request, Response, Depends
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

DB_PATH = ROOT / "cerberus_users.db"
SECRET_PATH = ROOT / "backend" / ".session_secret"
if not SECRET_PATH.exists():
    SECRET_PATH.write_text(secrets.token_urlsafe(48), encoding="utf-8")
SESSION_SERIALIZER = URLSafeTimedSerializer(SECRET_PATH.read_text(encoding="utf-8").strip(), salt="cerberus-x-session")
SESSION_COOKIE = "cerberus_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_auth_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
init_auth_db()

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
    return salt.hex() + "$" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 310000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False

def current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    try:
        payload = SESSION_SERIALIZER.loads(token, max_age=SESSION_MAX_AGE)
        with get_db() as conn:
            user = conn.execute("SELECT id, name, email FROM users WHERE id = ?", (payload.get("uid"),)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Your session is no longer valid. Please log in again.")
        return dict(user)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Your session expired. Please log in again.")

class RegisterData(BaseModel):
    name: str
    email: str
    password: str

class LoginData(BaseModel):
    email: str
    password: str

@app.post("/api/auth/register")
def register(payload: RegisterData, response: Response):
    name = payload.name.strip()
    email = payload.email.strip().lower()
    password = payload.password
    if len(name) < 2 or len(name) > 80:
        raise HTTPException(400, "Please enter a name between 2 and 80 characters.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Please enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(400, "Password must contain at least 8 characters.")
    try:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, email, hash_password(password), datetime.now().isoformat(timespec="seconds"))
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists. Please log in.")
    token = SESSION_SERIALIZER.dumps({"uid": user_id})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_MAX_AGE, path="/")
    return {"message": "Account created successfully.", "user": {"id": user_id, "name": name, "email": email}}

@app.post("/api/auth/login")
def login(payload: LoginData, response: Response):
    email = payload.email.strip().lower()
    with get_db() as conn:
        user = conn.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password.")
    token = SESSION_SERIALIZER.dumps({"uid": user["id"]})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_MAX_AGE, path="/")
    return {"message": "Login successful.", "user": {"id": user["id"], "name": user["name"], "email": user["email"]}}

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "Logged out."}

@app.get("/api/auth/me")
def auth_me(user=Depends(current_user)):
    return {"user": user}
# --- End authentication ---

user_states = {}

def state_for(user):
    key = str(user["id"])
    if key not in user_states:
        user_states[key] = {"documents": [], "facts": [], "conflicts": [], "graph": {"nodes": [], "edges": []}}
    return user_states[key]

class Question(BaseModel):
    question: str

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    try:
        current_user(request)
        page = "index.html"
    except HTTPException:
        page = "login.html"
    return (FRONTEND / page).read_text(encoding="utf-8")

@app.get("/api/status")
def status():
    return {"status": "running", "mode": "local prototype", "documents": sum(len(s["documents"]) for s in user_states.values())}

@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), user=Depends(current_user)):
    accepted = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".xlsx", ".xls", ".csv", ".txt", ".md"}
    user_state = state_for(user)
    processed, errors = [], []
    for upload in files:
        name = Path(upload.filename or "unnamed").name
        ext = Path(name).suffix.lower()
        if ext not in accepted:
            errors.append({"filename": name, "error": "Unsupported file type"})
            continue
        content = await upload.read()
        if len(content) > 15 * 1024 * 1024:
            errors.append({"filename": name, "error": "File exceeds 15 MB limit"})
            continue
        try:
            text, notes = extract_file(name, content)
            doc_id = str(uuid.uuid4())[:8]
            stored_name = f"{doc_id}_{name}"
            (UPLOAD_DIR / stored_name).write_bytes(content)
            doc = {
                "id": doc_id, "filename": name, "file_type": ext.lstrip(".").upper(),
                "uploaded_at": datetime.now().isoformat(timespec="seconds"),
                "characters": len(text), "status": "Processed" if text.strip() else "Needs OCR / no text",
                "notes": notes, "text": text
            }
            user_state["documents"].append(doc)
            new_facts = extract_facts(text, name)
            for f in new_facts:
                f["id"] = str(uuid.uuid4())[:8]
                f["document_id"] = doc_id
            user_state["facts"].extend(new_facts)
            processed.append({"id": doc_id, "filename": name, "characters": len(text), "facts": len(new_facts), "status": doc["status"], "notes": notes})
        except Exception as exc:
            errors.append({"filename": name, "error": str(exc)})
    user_state["conflicts"] = detect_contradictions(user_state["facts"])
    rebuild_graph(user_state)
    return {"processed": processed, "errors": errors, "summary": get_summary(user_state)}

def rebuild_graph(state):
    nodes, edges, seen = [], [], set()
    for fact in state["facts"]:
        subject = fact["key"].replace("_", " ").title()
        sid = "property:" + subject
        vid = "value:" + fact["value"]
        if sid not in seen:
            nodes.append({"id": sid, "label": subject, "kind": "property"})
            seen.add(sid)
        if vid not in seen:
            nodes.append({"id": vid, "label": fact["value"], "kind": "value"})
            seen.add(vid)
        edges.append({"from": sid, "to": vid, "label": fact["source"]})
    state["graph"] = {"nodes": nodes, "edges": edges}

def get_summary(state):
    return {
        "documents": len(state["documents"]),
        "facts": len(state["facts"]),
        "contradictions": len(state["conflicts"]),
        "needs_review": sum(1 for d in state["documents"] if d["status"] != "Processed")
    }

@app.get("/api/data")
def data(user=Depends(current_user)):
    user_state = state_for(user)
    docs = [{k:v for k,v in d.items() if k != "text"} for d in user_state["documents"]]
    return {"summary": get_summary(user_state), "documents": docs, "facts": user_state["facts"], "conflicts": user_state["conflicts"], "graph": user_state["graph"]}

@app.post("/api/chat")
def chat(payload: Question, user=Depends(current_user)):
    user_state = state_for(user)
    q = payload.question.strip()
    if not q:
        raise HTTPException(400, "Please enter a question.")
    terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", q) if len(t) > 2]
    ranked = []
    for fact in user_state["facts"]:
        hay = (fact["claim"] + " " + fact["key"] + " " + fact["value"]).lower()
        score = sum(1 for t in terms if t in hay)
        if score:
            ranked.append((score, fact))
    ranked.sort(key=lambda x: x[0], reverse=True)
    matches = [x[1] for x in ranked[:5]]
    if not matches:
        answer = "I could not find supporting evidence for that question in the uploaded documents. Please upload relevant evidence or ask a more specific question."
    else:
        lines = [f"• {f['claim']} (Source: {f['source']})" for f in matches]
        answer = "I found the following relevant evidence. This prototype retrieves matching extracted claims; it does not independently prove which claim is true:\n\n" + "\n".join(lines)
        relevant_conflicts = [c for c in user_state["conflicts"] if any(f["source"] in (c["source_a"], c["source_b"]) for f in matches)]
        if relevant_conflicts:
            answer += "\n\nWarning: related conflicting evidence exists. Review the contradiction panel before drawing a conclusion."
    return {"answer": answer, "evidence": matches, "mode": "local evidence retrieval prototype"}

@app.get("/api/report")
def report(user=Depends(current_user)):
    user_state = state_for(user)
    report_data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": get_summary(user_state),
        "documents": [{k:v for k,v in d.items() if k != "text"} for d in user_state["documents"]],
        "facts": user_state["facts"],
        "contradictions": user_state["conflicts"],
        "limitations": ["Prototype rule-based extraction", "Contradiction detection is limited to selected date categories", "Reliability is not yet scored", "No general-purpose local LLM is connected"]
    }
    path = REPORT_DIR / ("cerberus_evidence_report_user_" + str(user["id"]) + ".json")
    path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    return JSONResponse(report_data, headers={"Content-Disposition": "attachment; filename=cerberus_evidence_report.json"})

@app.delete("/api/reset")
def reset(user=Depends(current_user)):
    user_states.pop(str(user["id"]), None)
    return {"message": "Prototype session cleared."}