"""HMAC-signed short-lived ingress assertions for internal trusted callers.

Requires a high-entropy key configured out-of-band. This is not OAuth/OIDC
and does not validate external identity provider tokens.
"""
import base64
import hashlib
import hmac
import json
import time

from foundation_next.tenant_dispatch import AuthenticatedPrincipal


def _encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class SignedIngress:
    def __init__(self, secret: bytes, issuer: str, audience: str):
        if len(secret) < 32 or not issuer or not audience:
            raise ValueError("Strong secret, issuer and audience required")
        self.secret = secret
        self.issuer = issuer
        self.audience = audience

    def issue(self, *, subject: str, tenant_id: str, ttl_seconds: int = 300):
        if not subject or not tenant_id or not 0 < ttl_seconds <= 900:
            raise ValueError("Invalid assertion")
        payload = {"sub": subject, "tenant": tenant_id, "iss": self.issuer,
                   "aud": self.audience, "exp": int(time.time()) + ttl_seconds}
        body = _encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = _encode(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        return body + "." + signature

    def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            body, signature = token.split(".")
            expected = hmac.new(self.secret, body.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _decode(signature)):
                raise ValueError("Signature mismatch")
            claims = json.loads(_decode(body))
            if not isinstance(claims, dict) or claims.get("iss") != self.issuer:
                raise ValueError("Invalid issuer")
            if claims.get("aud") != self.audience or type(claims.get("exp")) is not int:
                raise ValueError("Invalid audience or expiry")
            if not int(time.time()) < claims["exp"] <= int(time.time()) + 900:
                raise ValueError("Expired or invalid lifetime")
            return AuthenticatedPrincipal(claims["sub"], claims["tenant"], self.issuer, True)
        except (ValueError, KeyError, TypeError, UnicodeError, OverflowError) as exc:
            raise PermissionError("Invalid ingress assertion") from exc
