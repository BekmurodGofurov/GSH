import os

with open('gateway-api/main.py', 'r') as f:
    content = f.read()

# Replace the env var loading block and verify_api_key
old_block1 = """
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not all([ADMIN_API_KEY, ADMIN_USERNAME, ADMIN_PASSWORD]):
    raise ValueError("ADMIN_API_KEY, ADMIN_USERNAME, and ADMIN_PASSWORD must be set in the .env file.")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return api_key
"""

new_block1 = """
import secrets
from fastapi import Request, Response

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
active_sessions = set()

async def verify_api_key(request: Request, api_key: str = Security(api_key_header)):
    if ADMIN_API_KEY and api_key:
        if secrets.compare_digest(api_key, ADMIN_API_KEY):
            return api_key
            
    session_token = request.cookies.get("admin_session")
    if session_token and session_token in active_sessions:
        return session_token
        
    raise HTTPException(status_code=403, detail="Unauthorized")
"""
content = content.replace(old_block1.strip(), new_block1.strip())

# Replace FRONTEND_URL
content = content.replace('FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")', 'FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")')

# Replace admin_login endpoint
old_block2 = """
@app.post("/api/v1/admin/login")
async def admin_login(creds: LoginRequest):
    if creds.username == ADMIN_USERNAME and creds.password == ADMIN_PASSWORD:
        return {"status": "success", "token": ADMIN_API_KEY}
    raise HTTPException(status_code=401, detail="Invalid credentials")
"""

new_block2 = """
@app.post("/api/v1/admin/login")
async def admin_login(creds: LoginRequest, response: Response):
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Admin feature disabled")
        
    if secrets.compare_digest(creds.username, ADMIN_USERNAME) and secrets.compare_digest(creds.password, ADMIN_PASSWORD):
        session_token = secrets.token_urlsafe(32)
        active_sessions.add(session_token)
        response.set_cookie(key="admin_session", value=session_token, httponly=True, samesite="lax")
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/v1/admin/me")
async def admin_me(api_key: str = Depends(verify_api_key)):
    return {"status": "authenticated"}

@app.post("/api/v1/admin/logout")
async def admin_logout(request: Request, response: Response):
    session_token = request.cookies.get("admin_session")
    if session_token in active_sessions:
        active_sessions.remove(session_token)
    response.delete_cookie("admin_session")
    return {"status": "success"}
"""
content = content.replace(old_block2.strip(), new_block2.strip())

# Fix docstring of POST /api/v1/servers
content = content.replace('"""Add or update a monitored CS2 server via Admin or Frontend"""', '"""Add or update a monitored CS2 server (requires admin API key)."""')

# Fix missing blank line before @app.put("/api/v1/servers/{server_id:path}")
content = content.replace('    return {"status": "success", "event_id": event_id, "root_cause": payload.root_cause, "label_source": "manual"}\n@app.put("/api/v1/servers/{server_id:path}")', '    return {"status": "success", "event_id": event_id, "root_cause": payload.root_cause, "label_source": "manual"}\n\n@app.put("/api/v1/servers/{server_id:path}")')

with open('gateway-api/main.py', 'w') as f:
    f.write(content)
