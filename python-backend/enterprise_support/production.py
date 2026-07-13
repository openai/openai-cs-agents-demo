from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    passed: bool
    message: str


def production_readiness_checks() -> list[ReadinessCheck]:
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env != "production":
        return [ReadinessCheck("environment", True, "Development mode; production gates are advisory")]

    database_url = os.getenv("DATABASE_URL", "")
    cors_origins = os.getenv("CORS_ORIGINS", "")
    auth_mode = os.getenv("AUTH_MODE", "").strip().lower()
    checks = [
        ReadinessCheck(
            "auth_mode",
            auth_mode in {"oidc", "roboage"},
            "AUTH_MODE must be oidc or roboage",
        ),
        ReadinessCheck(
            "database",
            database_url.startswith(("postgresql://", "postgresql+psycopg://")),
            "DATABASE_URL must point to PostgreSQL",
        ),
        ReadinessCheck(
            "encryption",
            bool(os.getenv("DATA_ENCRYPTION_KEY")),
            "DATA_ENCRYPTION_KEY is required",
        ),
        ReadinessCheck(
            "connector_mode",
            os.getenv("CONNECTOR_MODE") == "live",
            "CONNECTOR_MODE must be live",
        ),
        ReadinessCheck(
            "document_processing",
            os.getenv("DOCUMENT_PROCESSING_MODE") == "async",
            "DOCUMENT_PROCESSING_MODE must be async",
        ),
        ReadinessCheck(
            "object_storage",
            os.getenv("OBJECT_STORAGE_BACKEND") == "s3" and bool(os.getenv("S3_BUCKET")),
            "S3 object storage and bucket are required",
        ),
        ReadinessCheck(
            "malware_scanner",
            bool(os.getenv("CLAMAV_COMMAND")),
            "CLAMAV_COMMAND is required",
        ),
        ReadinessCheck(
            "tracing",
            os.getenv("OPENAI_TRACING_DISABLED", "1") == "1",
            "OpenAI tracing must remain disabled for the Zhipu runtime",
        ),
        ReadinessCheck(
            "cors",
            bool(cors_origins) and "localhost" not in cors_origins,
            "CORS_ORIGINS must contain production origins only",
        ),
        ReadinessCheck(
            "development_token",
            os.getenv("DEV_AUTH_TOKEN", "local-dev-token") == "local-dev-token",
            "DEV_AUTH_TOKEN is ignored outside development mode",
        ),
    ]
    if auth_mode == "roboage":
        checks.append(
            ReadinessCheck(
                "roboage_service_token",
                bool(os.getenv("ROBOAGE_INTERNAL_TOKEN")),
                "ROBOAGE_INTERNAL_TOKEN is required for RoboAge server-to-server mode",
            )
        )
    else:
        checks.extend(
            [
                ReadinessCheck(
                    "oidc_configuration",
                    all(
                        os.getenv(name)
                        for name in ("OIDC_ISSUER", "OIDC_AUDIENCE", "OIDC_JWKS_URL")
                    ),
                    "OIDC issuer, audience, and JWKS URL are required",
                ),
                ReadinessCheck(
                    "oidc_browser_flow",
                    all(
                        os.getenv(name)
                        for name in (
                            "OIDC_AUTHORIZATION_ENDPOINT",
                            "OIDC_TOKEN_ENDPOINT",
                            "OIDC_CLIENT_ID",
                            "OIDC_REDIRECT_URI",
                            "SESSION_SIGNING_KEY",
                        )
                    ),
                    "OIDC browser flow and session signing settings are required",
                ),
            ]
        )
    return checks


def assert_production_ready() -> None:
    checks = production_readiness_checks()
    failures = [check for check in checks if not check.passed]
    if failures and os.getenv("ENFORCE_PRODUCTION_GATES", "1") == "1":
        details = "; ".join(f"{check.name}: {check.message}" for check in failures)
        raise RuntimeError(f"Production readiness checks failed: {details}")
