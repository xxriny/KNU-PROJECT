"""
Lightweight ContextVar definitions — importable without pulling in LangChain/Gemini.
Rest handler and auth layers import from here instead of utils.py.
"""
from contextvars import ContextVar

active_usage_log: ContextVar[list] = ContextVar("active_usage_log", default=[])
active_session_id: ContextVar[str] = ContextVar("active_session_id", default="")
active_jwt_token: ContextVar[str] = ContextVar("active_jwt_token", default="")
