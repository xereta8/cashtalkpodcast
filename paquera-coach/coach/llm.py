"""Camada fina sobre a API do Claude: streaming, fallback em recusa e saída estruturada."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
from pathlib import Path

import anthropic

MODEL = os.environ.get("COACH_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _system_blocks(system: str) -> list[dict]:
    # O system prompt é estável dentro de um modo -> cacheável.
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


def stream_reply(system: str, messages: list[dict], effort: str = "medium", prefix: str = "") -> list:
    """Envia a conversa, imprime a resposta em tempo real e devolve o `content` completo
    (para ser anexado ao histórico sem alterações)."""
    if prefix:
        print(prefix, end="", flush=True)
    with client().beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=_system_blocks(system),
        messages=messages,
        output_config={"effort": effort},
        betas=[FALLBACK_BETA],
        fallbacks="default",
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
        final = stream.get_final_message()
    print()
    if final.stop_reason == "refusal":
        print("\n[O modelo recusou esse pedido. Tente reformular.]", file=sys.stderr)
    elif final.stop_reason == "max_tokens":
        print("\n[Resposta cortada por limite de tamanho.]", file=sys.stderr)
    return final.content


def extract_json(system: str, prompt: str, schema: dict) -> dict | None:
    """Chamada curta com saída estruturada (JSON garantido pelo schema)."""
    resp = client().beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        return None
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def image_block(path: str) -> dict:
    p = Path(path).expanduser()
    media_type = mimetypes.guess_type(p.name)[0] or "image/png"
    if media_type not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
        raise ValueError(f"Formato de imagem não suportado: {p.name}")
    data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
