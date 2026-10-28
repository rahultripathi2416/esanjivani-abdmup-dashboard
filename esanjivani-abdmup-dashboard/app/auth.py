import hmac
import hashlib
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

AUTHORIZED_USERS = {
    "abdm_admin": {"password_hash": hashlib.sha256(b"UPState@ABDM2026").hexdigest(), "role": "StateAdmin"},
    "abdm_reviewer": {"password_hash": hashlib.sha256(b"Reviewer#UP2026").hexdigest(), "role": "ProgramOfficer"}
}

def verify_abdm_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    user = AUTHORIZED_USERS.get(credentials.username)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized ABDM User ID", headers={"WWW-Authenticate": "Basic"})
    
    input_hash = hashlib.sha256(credentials.password.encode()).hexdigest()
    if not hmac.compare_digest(input_hash, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid ABDM Security Credentials", headers={"WWW-Authenticate": "Basic"})
    
    return {"username": credentials.username, "role": user["role"]}
