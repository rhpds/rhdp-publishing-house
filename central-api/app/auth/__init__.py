"""Authentication modules."""
from .oidc import init_oidc, require_oidc_auth, get_oidc_validator
from .groups import (
    GROUP_BITS, ALL_GROUPS_MASK, compute_bitmask,
    lookup_user_groups, create_signed_key, decode_signed_key,
)
from .token_cache import (
    cache_token, get_cached_token, is_token_in_cache,
    revoke_token, revoke_all_tokens, list_tokens, search_tokens,
    save_backup, load_backup,
)

__all__ = [
    "init_oidc", "require_oidc_auth", "get_oidc_validator",
    "GROUP_BITS", "ALL_GROUPS_MASK", "compute_bitmask",
    "lookup_user_groups", "create_signed_key", "decode_signed_key",
    "cache_token", "get_cached_token", "is_token_in_cache",
    "revoke_token", "revoke_all_tokens", "list_tokens", "search_tokens",
    "save_backup", "load_backup",
]
