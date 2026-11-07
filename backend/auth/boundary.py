"""Same-origin JSON write boundaries and no-store, including errors."""
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


class AuthBoundary:
    def __init__(self, app, origin):
        self.app, self.origin = app, origin

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not (scope["path"] == "/search" or scope["path"].startswith(("/auth/", "/admin/", "/pages/"))):
            await self.app(scope, receive, send)
            return

        started = False

        async def no_store(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "private, no-store"
                headers["Vary"] = "Cookie"
            await send(message)

        async def reject(code, detail):
            await JSONResponse({"detail": detail}, status_code=code)(scope, receive, no_store)

        if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            headers = Headers(scope=scope)
            if headers.getlist("origin") != [self.origin] or headers.get("sec-fetch-site") == "cross-site":
                await reject(403, "ORIGIN_REJECTED")
                return
            if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                await reject(415, "JSON_REQUIRED")
                return
            body = b""
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body += message.get("body", b"")
                if len(body) > 8192:
                    await reject(413, "BODY_TOO_LARGE")
                    return
                if not message.get("more_body"):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            try:
                await self.app(scope, replay, no_store)
            except SQLAlchemyError:
                if started:
                    raise
                await reject(503, "SERVICE_UNAVAILABLE")
        else:
            try:
                await self.app(scope, receive, no_store)
            except SQLAlchemyError:
                if started:
                    raise
                await reject(503, "SERVICE_UNAVAILABLE")
