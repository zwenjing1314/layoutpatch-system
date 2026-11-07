"""Same-origin JSON write boundaries and no-store, including errors."""
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


class AuthBoundary:
    def __init__(self, app, origin, upload_max_bytes=20 * 1024 * 1024):
        self.app, self.origin = app, origin
        self.upload_max_bytes = upload_max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not (scope["path"] in ("/search", "/index", "/documents", "/jobs") or scope["path"].startswith(("/auth/", "/admin/", "/pages/", "/documents/", "/jobs/"))):
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
            upload = scope["path"] == "/index" and scope["method"] == "POST"
            required_type = "multipart/form-data" if upload else "application/json"
            if len(headers.getlist("content-type")) != 1 or headers.get("content-type", "").split(";", 1)[0].strip().lower() != required_type:
                await reject(415, "MULTIPART_REQUIRED" if upload else "JSON_REQUIRED")
                return
            body = bytearray()
            maximum = self.upload_max_bytes + 65536 if upload else 8192
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body += message.get("body", b"")
                if len(body) > maximum:
                    await reject(413, "BODY_TOO_LARGE")
                    return
                if not message.get("more_body"):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
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
