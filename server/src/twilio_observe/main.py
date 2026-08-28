from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from twilio_observe.config import settings
from twilio_observe.routes.sessions import router as sessions_router
from twilio_observe.routes.coach import router as coach_router
from twilio_observe.routes.barge import router as barge_router
from twilio_observe.routes.tokens import router as tokens_router
from twilio_observe.routes.calls import router as calls_router
from twilio_observe.relay.handler import handle_relay_connection
from twilio_observe.tac.ci_middleware import CIEventCaptureMiddleware

app = FastAPI(title="Twilio Observe Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# CI Event Capture — receives Conversation Intelligence operator webhooks
ci_middleware = CIEventCaptureMiddleware(path="/ci-webhook")

app.include_router(sessions_router)
app.include_router(coach_router)
app.include_router(barge_router)
app.include_router(tokens_router)
app.include_router(calls_router)
app.include_router(ci_middleware.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/relay/{call_sid}")
async def websocket_relay(ws: WebSocket, call_sid: str):
    await handle_relay_connection(ws, call_sid)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("twilio_observe.main:app", host="0.0.0.0", port=settings.port, reload=True)
