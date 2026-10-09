"""Per-request cloud identity credential context for local Desktop inference."""

from contextvars import ContextVar

current_cloud_identity_token: ContextVar[str] = ContextVar("cloud_identity_token", default="")
