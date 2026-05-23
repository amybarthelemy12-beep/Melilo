"""Translator backends.

A `translator` is any callable that takes a list of chat messages and returns a
string. Two implementations:

- `HFLocalTranslator`     : loads an HF causal-LM in-process. Default.
- `OpenAICompatTranslator`: hits any OpenAI-compatible HTTP API. Works with
                            local Ollama, hosted providers (Parasail, OpenRouter,
                            etc.), vLLM-served endpoints — anything that speaks
                            `/v1/chat/completions`. Swap providers by changing
                            OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL.

`load_translator(...)` picks one based on `settings.backend`. The same callable
shape (`(list[dict]) -> str`) is returned in both cases, so the rest of the
pipeline is backend-agnostic.
"""
from __future__ import annotations

from typing import Callable

from melilo.config import settings


Translator = Callable[[list[dict]], str]


def _load_hf() -> Translator:
    """Original in-process HF transformers loader. Use this when you have a GPU
    and want everything in one Python process."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(settings.translator_model)
    model = AutoModelForCausalLM.from_pretrained(
        settings.translator_model, device_map="auto", torch_dtype="auto"
    )

    def _call(messages: list[dict]) -> str:
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        out = model.generate(
            **inputs,
            max_new_tokens=settings.backend_max_tokens,
            do_sample=settings.backend_temperature > 0,
            temperature=max(settings.backend_temperature, 1e-5),
        )
        return tok.decode(
            out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        ).strip()

    return _call


def _load_openai_compat() -> Translator:
    """OpenAI-compatible HTTP backend. The OpenAI Python SDK speaks /v1/chat/
    completions, which is what Ollama / Parasail / OpenRouter / vLLM all serve.

    A single `OpenAI` client is created at load time and reused across calls.
    The client is thread-safe so the backfill driver can submit concurrent
    requests from a thread pool."""
    from openai import OpenAI

    client = OpenAI(base_url=settings.openai_base_url, api_key=settings.openai_api_key)
    model = settings.openai_model

    # Provider-specific opt-outs we add when talking to OpenRouter. These are
    # ignored by other providers that don't recognize them. Cheap to always send.
    extra_body: dict = {}
    if "openrouter" in settings.openai_base_url:
        extra_body = {
            "provider": {"data_collection": "deny", "allow_fallbacks": True},
        }

    def _call(messages: list[dict]) -> str:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=settings.backend_max_tokens,
            temperature=settings.backend_temperature,
            extra_body=extra_body or None,
        )
        return (resp.choices[0].message.content or "").strip()

    return _call


def load_translator() -> Translator:
    """Build the translator callable. Backend choice comes from
    `settings.backend` (defaults to `hf`)."""
    backend = settings.backend.lower().strip()
    if backend == "hf":
        return _load_hf()
    if backend in {"openai", "ollama", "parasail", "openrouter", "vllm"}:
        # All of these speak the OpenAI chat-completions API; the alias is just
        # for documentation. The real provider is determined by OPENAI_BASE_URL.
        return _load_openai_compat()
    raise ValueError(
        f"unknown MELILO_BACKEND={settings.backend!r}; "
        "valid: hf, openai (or aliases: ollama, parasail, openrouter, vllm)"
    )
