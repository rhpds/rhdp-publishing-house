"""Authentication modules."""
from .oidc import init_oidc, require_oidc_auth

__all__ = ["init_oidc", "require_oidc_auth"]
