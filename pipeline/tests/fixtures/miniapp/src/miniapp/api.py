"""HTTP API (FastAPI-style)."""

from fastapi import APIRouter, FastAPI

from miniapp.core import top_level

app = FastAPI()
router = APIRouter()


@app.get("/items/{item_id}")
def read_item(item_id):
    return top_level(item_id)


@router.post("/items")
def create_item(payload):
    return top_level(payload)


@app.websocket("/ws")
def ws(sock):
    return sock
