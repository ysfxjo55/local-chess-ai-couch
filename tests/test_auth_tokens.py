from jose import jwt

from backend.app.auth import JWT_ALGORITHM, create_access_token
from backend.app.config import settings


def test_access_token_carries_required_security_claims():
    token = create_access_token(user_id=7, username="coach", token_version=3)
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM], audience=settings.JWT_AUDIENCE, issuer=settings.JWT_ISSUER)
    assert payload["uid"] == 7
    assert payload["sub"] == "coach"
    assert payload["ver"] == 3
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["aud"] == settings.JWT_AUDIENCE
    assert payload["jti"]
