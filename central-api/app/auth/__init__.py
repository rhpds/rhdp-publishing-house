"""Authentication modules."""
from .oidc import init_oidc, require_oidc_auth, get_oidc_validator
from .groups import (
    GROUP_BITS, ALL_GROUPS_MASK, compute_bitmask,
    lookup_user_groups, create_signed_key, decode_signed_key,
)

__all__ = [
    "init_oidc", "require_oidc_auth", "get_oidc_validator",
    "GROUP_BITS", "ALL_GROUPS_MASK", "compute_bitmask",
    "lookup_user_groups", "create_signed_key", "decode_signed_key",
]
