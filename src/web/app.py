"""FastAPI web application entry point for webhook and OAuth callbacks (Architecture B).

Covers:
- SEC-006, SEC-010: Webhook authentication via X-Telegram-Bot-Api-Secret-Token (T-WEB-01).
- Idempotent update handling via telegram_updates table.
- Healthcheck endpoint /health.
- Web-based OAuth redirect callback /callback/linkedin.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import Update

from src.config import Settings, load_settings
from src.db.models import TelegramUpdate
from src.db.session import create_db_engine, get_session_factory
from src.services.linkedin_oauth_service import LinkedInOAuthService
from src.telegram_bot.bot import build_bot_app

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    init_bot: bool = True,
) -> FastAPI:
    """Application factory for FastAPI webhook server."""
    app_settings = settings or load_settings()

    if session_factory is None:
        engine = create_db_engine(app_settings.database_url)
        session_factory = get_session_factory(engine)

    bot_app = build_bot_app(app_settings, session_factory=session_factory)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Manage bot application lifecycle."""
        if init_bot:
            try:
                await bot_app.initialize()
                await bot_app.start()
            except Exception as e:
                logger.warning("Bot initialization skipped in lifespan: %s", e)

        app.state.bot_app = bot_app
        app.state.settings = app_settings
        app.state.session_factory = session_factory
        yield
        if init_bot:
            try:
                await bot_app.stop()
                await bot_app.shutdown()
            except Exception as e:
                logger.debug("Bot shutdown error: %s", e)

    app = FastAPI(
        title="LinkedIn Telegram AI Assistant",
        description="Private single-owner LinkedIn assistant bot",
        lifespan=lifespan,
    )
    app.state.bot_app = bot_app
    app.state.settings = app_settings
    app.state.session_factory = session_factory

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Liveness probe for host monitoring and health checking."""
        return {"status": "ok", "app": "linkedin-telegram-ai-assistant"}

    @app.post("/webhook/telegram")
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(
            None, alias="X-Telegram-Bot-Api-Secret-Token"
        ),
    ) -> Response:
        """Receive inbound Telegram updates via authenticated webhook (SEC-010, T-WEB-01)."""
        current_settings: Settings = app.state.settings

        # Check webhook secret token (T-WEB-01)
        expected_secret = current_settings.telegram_webhook_secret
        if expected_secret:
            if (
                not x_telegram_bot_api_secret_token
                or x_telegram_bot_api_secret_token != expected_secret
            ):
                logger.warning("Rejected webhook request with invalid or missing secret token.")
                raise HTTPException(status_code=403, detail="Forbidden: Invalid secret token.")

        data = await request.json()
        update_id = data.get("update_id")

        if update_id is not None:
            db_factory: sessionmaker[Session] = app.state.session_factory
            with db_factory() as session:
                existing = session.execute(
                    select(TelegramUpdate).where(TelegramUpdate.update_id == update_id)
                ).scalar_one_or_none()

                if existing:
                    # Idempotent ignore: update was already processed
                    return Response(
                        content='{"ok": true, "note": "duplicate"}',
                        media_type="application/json",
                    )

                # Record processed update
                session.add(TelegramUpdate(update_id=update_id))
                session.commit()

        # Dispatch update to python-telegram-bot
        current_bot_app = app.state.bot_app
        update = Update.de_json(data, current_bot_app.bot)
        await current_bot_app.process_update(update)

        return Response(content='{"ok": true}', media_type="application/json")

    @app.get("/callback/linkedin", response_class=HTMLResponse)
    async def linkedin_oauth_callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> HTMLResponse:
        """Browser redirect URI callback for completing LinkedIn OAuth 2.0 flow."""
        current_settings: Settings = app.state.settings
        db_factory: sessionmaker[Session] = app.state.session_factory

        if error:
            return HTMLResponse(
                content=(
                    "<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                    f"<h2 style='color:#d9534f;'>❌ LinkedIn Authorization Error</h2>"
                    f"<p>{error}</p>"
                    "<p>Please return to Telegram and run /connect to try again.</p>"
                    "</body></html>"
                ),
                status_code=400,
            )

        if not code or not state:
            return HTMLResponse(
                content=(
                    "<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                    "<h2 style='color:#d9534f;'>❌ Missing Parameters</h2>"
                    "<p>Missing code or state parameters from LinkedIn response.</p>"
                    "</body></html>"
                ),
                status_code=400,
            )

        redirect_uri = current_settings.linkedin_redirect_url or "https://localhost/callback"

        with db_factory() as session:
            service = LinkedInOAuthService(
                session, encryption_key=current_settings.token_encryption_key
            )
            try:
                res = await service.exchange_code_for_token(
                    code=code,
                    state_str=state,
                    client_id=current_settings.linkedin_client_id,
                    client_secret=current_settings.linkedin_client_secret,
                    redirect_uri=redirect_uri,
                )
            except Exception as e:
                logger.error("OAuth callback exchange failed: %s", e)
                return HTMLResponse(
                    content=(
                        "<html><body style='font-family:sans-serif;text-align:center;'>"
                        f"<h2 style='color:#d9534f;'>❌ Connection Failed</h2>"
                        f"<p>{e}</p>"
                        "<p>Please return to Telegram and run /connect to try again.</p>"
                        "</body></html>"
                    ),
                    status_code=400,
                )

        return HTMLResponse(
            content=(
                "<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                "<h2 style='color:#5cb85c;'>✅ LinkedIn Connected Successfully!</h2>"
                f"<p>Connected as member: <b>{res['member_urn']}</b></p>"
                f"<p>Access token is valid for <b>{res['days_valid']} days</b>.</p>"
                "<p>You can now close this tab and return to Telegram.</p>"
                "</body></html>"
            ),
            status_code=200,
        )

    return app


# Module-level default app instance for Uvicorn
try:
    app = create_app()
except Exception:  # pragma: no cover
    app = None
