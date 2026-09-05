"""
Authentication Manager — Security & Token Management.

Validates credentials against environment variables and manages session tokens.
"""
import os
import secrets
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security_scheme = HTTPBearer(auto_error=False)


class AuthManager:
    """Manages authentication tokens and credential validation."""

    def __init__(self):
        self.admin_user = os.getenv("KILLPOINT_ADMIN_USER", "admin")
        self.admin_pass = os.getenv("KILLPOINT_ADMIN_PASS", "killpoint2026!")
        self.secret_key = os.getenv("KILLPOINT_SECRET_KEY", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        
        # Valid active session tokens set
        self._active_tokens: set[str] = set()
        
        # Default dev token for convenience
        self._default_token = "kp_session_" + secrets.token_hex(16)
        self._active_tokens.add(self._default_token)

    def authenticate(self, username: str, password: str) -> str | None:
        """Validate credentials and return token if valid."""
        user_ok = secrets.compare_digest(username, self.admin_user)
        pass_ok = secrets.compare_digest(password, self.admin_pass)
        
        if user_ok and pass_ok:
            token = f"kp_session_{secrets.token_hex(16)}"
            self._active_tokens.add(token)
            return token
        return None

    def validate_token(self, token: str) -> bool:
        """Check if session token is active."""
        if not token:
            return False
        return token in self._active_tokens


auth_manager = AuthManager()


def require_auth(credentials: HTTPAuthorizationCredentials | None = Security(security_scheme)) -> str:
    """FastAPI Dependency enforcing authentication on protected routes."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Authentication required to access KillPoint verification APIs",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    if not auth_manager.validate_token(token):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "admin"
