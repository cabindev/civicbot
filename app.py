"""Main entry point: aiohttp web server exposing /api/messages."""

import logging
import sys
import traceback

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import TurnContext
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.schema import Activity, ActivityTypes

from bot import CivicSpaceBot
from config import Config
from gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Bot Framework adapter & authentication -------------------------------
ADAPTER = CloudAdapter(ConfigurationBotFrameworkAuthentication(Config))


async def on_error(context: TurnContext, error: Exception):
    """Catch-all error handler for the adapter."""
    logger.error("Unhandled error: %s", error, exc_info=error)
    traceback.print_exc()
    await context.send_activity(
        "ขออภัยค่ะ เกิดข้อผิดพลาดในระบบ กรุณาลองใหม่อีกครั้งนะคะ"
    )


ADAPTER.on_turn_error = on_error

# --- Bot instance ---------------------------------------------------------
BOT = CivicSpaceBot(GeminiClient())


# --- HTTP handlers --------------------------------------------------------
async def messages(req: Request) -> Response:
    """Main bot endpoint. Azure Bot Service POSTs activities here."""
    if "application/json" not in req.headers.get("Content-Type", ""):
        return Response(status=415)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    response = await ADAPTER.process_activity(auth_header, activity, BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=201)


async def health(_req: Request) -> Response:
    """Simple health probe for Azure App Service."""
    return json_response({"status": "ok", "service": "civicspace-bot"})


def init_func(argv=None):
    """Application factory used by `python -m aiohttp.web` / gunicorn."""
    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/", health)
    return app


APP = init_func()


if __name__ == "__main__":
    try:
        web.run_app(APP, host="0.0.0.0", port=Config.PORT)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to start app: %s", exc)
        raise
