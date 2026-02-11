# AlphaWheel Pro - Helpers de sesión (usuario logueado y cuenta activa)
import streamlit as st

from database import db


def get_current_user_id():
    """Usuario actual (sesión logueada). None si no hay sesión."""
    return st.session_state.get("user_id")


def get_current_user_email():
    return st.session_state.get("user_email", "")


def get_current_user_display_name():
    return st.session_state.get("user_display_name", "")


def get_current_account_id():
    return st.session_state.get("current_account_id")


def set_current_account_id(account_id):
    st.session_state["current_account_id"] = account_id


def get_accounts_for_current_user():
    """Cuentas del usuario logueado."""
    user_id = get_current_user_id()
    if not user_id:
        return []
    return db.get_accounts_by_user(user_id)
