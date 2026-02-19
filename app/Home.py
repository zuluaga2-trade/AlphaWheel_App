# AlphaWheel Pro - Punto de entrada: autenticación multi-usuario
# Ejecutar: streamlit run app/Home.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from database.db import init_db, get_user_by_email
from auth.auth import login_user, register_user, is_logged_in, logout_user, get_last_login_email, set_last_login_email
from app.styles import PROFESSIONAL_CSS

# set_page_config debe ser la primera llamada a Streamlit (requisito de Streamlit)
st.set_page_config(
    page_title="AlphaWheel Pro",
    layout="wide",
    page_icon="🦅",
    initial_sidebar_state="expanded",
    menu_items={"Get help": None, "Report a Bug": None, "About": None},
)
st.markdown(PROFESSIONAL_CSS, unsafe_allow_html=True)

try:
    init_db()
except Exception as e:
    st.error("No se pudo conectar a la base de datos. Si usas Streamlit Cloud, configura **ALPHAWHEEL_DATABASE_URL** en Secrets (PostgreSQL).")
    with st.expander("Detalle del error"):
        st.code(str(e))
    st.stop()


def render_login_register():
    """Pantalla de login y registro."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<p class='login-title'>🦅 AlphaWheel Pro</p>", unsafe_allow_html=True)
        st.markdown("<p class='login-subtitle'>Control de estrategias de opciones · Multi-usuario · Multi-cuenta</p>", unsafe_allow_html=True)
        st.caption("Si el navegador pregunta si guardar contraseña o datos del formulario, puedes elegir **No guardar**; la app guarda tu sesión mientras no cierres el navegador.")
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["Iniciar sesión", "Registrarse"])
        with tab_login:
            with st.form("login_form"):
                last_email = get_last_login_email()
                email_login = st.text_input(
                    "Email",
                    value=last_email,
                    placeholder="tu@email.com",
                    key="login_email",
                ).strip().lower()
                password_login = st.text_input("Contraseña", type="password", key="login_pass")
                if st.form_submit_button("Entrar"):
                    if email_login and password_login:
                        user_id = login_user(email_login, password_login)
                        if user_id:
                            set_last_login_email(email_login)
                            user = get_user_by_email(email_login)
                            st.session_state["logged_in"] = True
                            st.session_state["user_id"] = user_id
                            st.session_state["user_email"] = user["email"]
                            st.session_state["user_display_name"] = user.get("display_name") or user["email"]
                            st.rerun()
                        else:
                            st.error("Email o contraseña incorrectos.")
                    else:
                        st.warning("Completa email y contraseña.")

        with tab_register:
            with st.form("register_form"):
                email_reg = st.text_input("Email", placeholder="tu@email.com", key="reg_email").strip().lower()
                name_reg = st.text_input("Nombre (opcional)", placeholder="Tu nombre", key="reg_name")
                password_reg = st.text_input("Contraseña (mín. 6)", type="password", key="reg_pass")
                if st.form_submit_button("Crear cuenta"):
                    if email_reg and password_reg:
                        user_id, err = register_user(email_reg, name_reg, password_reg)
                        if user_id:
                            user = get_user_by_email(email_reg)
                            st.session_state["logged_in"] = True
                            st.session_state["user_id"] = user_id
                            st.session_state["user_email"] = user["email"]
                            st.session_state["user_display_name"] = user.get("display_name") or user["email"]
                            st.success("Cuenta creada. Bienvenido.")
                            st.rerun()
                        else:
                            if err and "ya existe" in err.lower():
                                st.error("Ya existe un usuario con ese email. Usa la pestaña **Iniciar sesión** para entrar con esa cuenta.")
                            else:
                                st.error(err or "Error al registrar.")
                    else:
                        st.warning("Email y contraseña obligatorios.")

        st.markdown("</div>", unsafe_allow_html=True)


if not is_logged_in():
    render_login_register()
    st.stop()

# Usuario logueado: cargar cockpit principal
from app.cockpit import run
run()
