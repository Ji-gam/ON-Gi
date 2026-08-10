"""전역 테스트 환경변수. auth_kit/security_kit이 import 시점에 이 값들을 읽으므로,
어떤 테스트 모듈이 그 패키지를 import하기 전에 먼저 세팅되어야 한다.
"""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production-needs-32-bytes-minimum")
os.environ.setdefault("PII_HASH_KEY", "test-phone-hash-key")
os.environ.setdefault("REQUIRE_EMAIL_VERIFICATION", "false")
os.environ.setdefault("REQUIRE_PHONE_VERIFICATION", "false")
os.environ.setdefault("COOKIE_SECURE", "false")

try:
    from cryptography.fernet import Fernet

    os.environ.setdefault("PII_ENCRYPTION_KEY", Fernet.generate_key().decode())
except ImportError:  # pragma: no cover
    pass
