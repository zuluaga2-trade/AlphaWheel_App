# AlphaWheel Pro - Autenticación: hash de contraseña y login/registro
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Tuple

from database import db

try:
    from config import ALLOWED_EMAILS, DATABASE_URL
except ImportError:
    ALLOWED_EMAILS = None
    DATABASE_URL = ""


def _is_shared_env() -> bool:
    """True si la app es multi-usuario/nube: no recordar último email (evitar que un usuario vea el de otro)."""
    if ALLOWED_EMAILS is not None:
        return True
    try:
        url = (DATABASE_URL or "").strip()
        return "postgresql" in url
    except Exception:
        return False


def _is_email_allowed(email: str) -> bool:
    """True si no hay lista de permitidos o si el email está en ella (comparación en minúsculas)."""
    if ALLOWED_EMAILS is None:
        return True
    return (email or "").strip().lower() in ALLOWED_EMAILS


def _hash_with_salt(password: str, salt: str) -> str:
    """Genera hash SHA-256 de salt + password."""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Genera salt:hash para almacenar en BD. Formato: 'salt_hex:hash_hex'."""
    salt = secrets.token_hex(16)
    h = _hash_with_salt(password, salt)
    return f"{salt}:{h}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    """Verifica contraseña contra valor almacenado (salt:hash)."""
    if not stored or ":" not in stored:
        return False
    salt, hash_val = stored.split(":", 1)
    return secrets.compare_digest(_hash_with_salt(password, salt), hash_val)


def login_user(email: str, password: str) -> Optional[int]:
    """
    Intento de login. Devuelve user_id si éxito, None si fallo.
    Si ALLOWED_EMAILS está definido, solo los emails de la lista pueden entrar.
    """
    email_n = (email or "").strip().lower()
    if not _is_email_allowed(email_n):
        return None
    user = db.get_user_by_email(email_n)
    if not user or not verify_password(password, user.get("password_hash")):
        return None
    return user["user_id"]


def register_user(email: str, display_name: str, password: str) -> Tuple[Optional[int], str]:
    """
    Registro de nuevo usuario. Devuelve (user_id, "") si éxito, (None, "mensaje_error") si fallo.
    Si ALLOWED_EMAILS está definido, solo los emails de la lista pueden registrarse.
    """
    email = email.strip().lower()
    if not email:
        return None, "El email es obligatorio."
    if not _is_email_allowed(email):
        return None, "Acceso no autorizado. Tu email no está en la lista de usuarios permitidos. Contacta al administrador."
    if not password or len(password) < 6:
        return None, "La contraseña debe tener al menos 6 caracteres."
    existing = db.get_user_by_email(email)
    if existing:
        return None, "Ya existe un usuario con ese email."
    try:
        password_hash = hash_password(password)
        user_id = db.create_user_with_password(email, display_name or email, password_hash)
        return user_id, ""
    except Exception as e:
        return None, str(e)


def logout_user():
    """Limpia sesión (llamar desde UI)."""
    import streamlit as st
    for key in ("logged_in", "user_id", "user_email", "user_display_name", "current_account_id"):
        if key in st.session_state:
            del st.session_state[key]


def is_logged_in() -> bool:
    """Comprueba si hay usuario logueado en session_state."""
    import streamlit as st
    return bool(st.session_state.get("logged_in") and st.session_state.get("user_id"))


def _last_login_file() -> Path:
    """Ruta del archivo donde guardamos el último email (recordar dispositivo)."""
    root = Path(__file__).resolve().parent.parent
    streamlit_dir = root / ".streamlit"
    streamlit_dir.mkdir(exist_ok=True)
    return streamlit_dir / "last_login_email"


def get_last_login_email() -> str:
    """Devuelve el último email con el que se inició sesión (para pre-rellenar). En modo multi-usuario/nube no se usa para no mostrar el email de otro usuario."""
    if _is_shared_env():
        return ""
    try:
        p = _last_login_file()
        if p.exists():
            return p.read_text(encoding="utf-8").strip().lower() or ""
    except Exception:
        pass
    return ""


def set_last_login_email(email: str) -> None:
    """Guarda el email tras un login exitoso. En modo multi-usuario/nube no se guarda (cada usuario es independiente)."""
    if _is_shared_env():
        return
    try:
        email = (email or "").strip().lower()
        if email:
            _last_login_file().write_text(email, encoding="utf-8")
    except Exception:
        pass
