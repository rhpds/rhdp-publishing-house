"""OIDC authentication for portal endpoints."""
import logging
from typing import Optional

import httpx
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

logger = logging.getLogger(__name__)


class OIDCAuth:
    """OIDC/Keycloak authentication validator."""

    def __init__(self, issuer_url: str, client_id: str):
        """Initialize OIDC auth with Keycloak issuer."""
        self.issuer_url = issuer_url.rstrip("/")
        self.client_id = client_id
        self._public_key = None
        self._jwks_uri = None

    async def _get_public_key(self) -> str:
        """Fetch Keycloak public key from OIDC discovery."""
        if self._public_key:
            return self._public_key

        # Get OIDC configuration
        config_url = f"{self.issuer_url}/.well-known/openid-configuration"
        async with httpx.AsyncClient(verify=False) as client:
            try:
                response = await client.get(config_url, timeout=10)
                response.raise_for_status()
                config = response.json()
                self._jwks_uri = config.get("jwks_uri")

                # Get public keys
                jwks_response = await client.get(self._jwks_uri, timeout=10)
                jwks_response.raise_for_status()
                jwks = jwks_response.json()

                # Extract first key (assuming single signing key)
                if jwks.get("keys"):
                    key_data = jwks["keys"][0]
                    # Construct PEM from JWK
                    from jose.backends import RSAKey
                    rsa_key = RSAKey(key_data, algorithm="RS256")
                    self._public_key = rsa_key.to_pem().decode()
                    return self._public_key

            except Exception as e:
                logger.error("Failed to fetch OIDC public key: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="OIDC configuration unavailable"
                )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No public key found in OIDC configuration"
        )

    async def validate_token(self, request: Request) -> str:
        """
        Validate JWT token from Authorization header or cookie.
        Returns user email from token claims.
        """
        # Try Authorization header first
        auth_header = request.headers.get("authorization", "")
        token = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            # Try cookie (for browser requests)
            token = request.cookies.get("access_token")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No token provided - please log in via Keycloak",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Get public key for verification
            public_key = await self._get_public_key()

            # Decode and validate JWT
            # Note: Skip audience validation as openshift realm doesn't include aud claim by default
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=self.issuer_url,
                options={"verify_aud": False}
            )

            # Extract email from claims
            email = payload.get("email") or payload.get("preferred_username")
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing email claim"
                )

            logger.info("OIDC auth successful for: %s", email)
            return email

        except JWTError as e:
            logger.warning("JWT validation failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error("Token validation error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token validation failed"
            )


# Global OIDC validator (initialized in main.py)
_oidc_validator: Optional[OIDCAuth] = None


def init_oidc(issuer_url: str, client_id: str):
    """Initialize global OIDC validator."""
    global _oidc_validator
    _oidc_validator = OIDCAuth(issuer_url, client_id)


async def require_oidc_auth(request: Request) -> str:
    """Dependency for OIDC-protected endpoints. Returns user email."""
    if not _oidc_validator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC not configured"
        )
    return await _oidc_validator.validate_token(request)
