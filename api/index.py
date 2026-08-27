async def app(scope, receive, send):
    from starlette.responses import JSONResponse

    resp = JSONResponse({"ok": True, "msg": "minimal handler works"})
    await resp(scope, receive, send)
