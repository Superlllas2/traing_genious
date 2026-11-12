"""Talking to the model: Ollama's own API, or any OpenAI compatible server (vLLM, LM Studio, a cloud API)."""

import json
import re
import time

from common import HTTPError, TimedOut, Unreachable, log, post_json


class ModelDown(RuntimeError):
    """The model server is not answering at all. The researcher pauses and tries again later."""


class ModelError(RuntimeError):
    """One request failed (too long, timed out, broken answer). The researcher skips that item."""


_think_fallback = {}   # (model, wanted setting) -> the setting that actually works for that model
LAST = {}              # token counts of the last answer: prompt, output, why it stopped, the context size
_no_format = set()     # models that refuse structured output


def chat(llm, system, user, think=None, schema=None, max_tokens=2000):
    if llm.get("api", "ollama") == "ollama":
        return _ollama(llm, system, user, think, schema, max_tokens)
    return _openai(llm, system, user, think, schema, max_tokens)


def _ollama(llm, system, user, think, schema, max_tokens):
    base = llm["base_url"].rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    model = llm["model"]
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "keep_alive": llm.get("keep_alive", "60m"),
        "options": {
            "temperature": llm.get("temperature", 0.3),
            "num_ctx": llm.get("num_ctx", 32768),
            "num_predict": max_tokens,
        },
    }
    think_key = (model, repr(think))
    think_value = _think_fallback.get(think_key, think)
    if think_value is not None:
        payload["think"] = think_value
    if schema is not None and model not in _no_format:
        payload["format"] = schema
    for attempt in range(5):
        try:
            answer = post_json(base + "/api/chat", payload, timeout=llm.get("timeout_seconds", 900))
            content = (answer.get("message") or {}).get("content") or ""
            LAST.clear()
            LAST.update(prompt=answer.get("prompt_eval_count") or 0, output=answer.get("eval_count") or 0,
                        stop=answer.get("done_reason"), num_ctx=payload["options"]["num_ctx"], max_tokens=max_tokens)
            if LAST["prompt"] + max_tokens > LAST["num_ctx"]:
                # Ollama cuts a prompt that does not fit, silently; say so
                log.warning("The prompt (%d tokens) plus the answer budget (%d) exceed the context (%d): "
                            "the start of the prompt may have been cut.", LAST["prompt"], max_tokens, LAST["num_ctx"])
            if not content.strip() and answer.get("done_reason") == "length":
                # The thinking used up num_predict before any answer came: say so instead of failing silently.
                log.warning("The model hit its limit of %d tokens before answering (thinking: %s). "
                            "Raise the max_tokens setting or switch thinking off for this step.",
                            max_tokens, payload.get("think"))
            return content
        except HTTPError as error:
            text = str(error).lower()
            if "think" in text and "think" in payload:
                # This model doesn't support that thinking setting: try "off", then no setting at all.
                if isinstance(payload["think"], str):
                    payload["think"] = False
                else:
                    payload.pop("think")
                _think_fallback[think_key] = payload.get("think")
                continue
            if "format" in payload and (any(word in text for word in ("format", "schema", "grammar", "json"))
                                        or error.code in (400, 500, 501)):
                # Some models or engines can't do structured output: ask again without it, and remember.
                payload.pop("format")
                _no_format.add(model)
                continue
            if error.code == 404:
                raise ModelDown(f'the model "{model}" is not downloaded. Run: ollama pull {model}') from None
            if error.code >= 500 and attempt == 0:
                time.sleep(10)
                continue
            raise ModelError(str(error)) from None
        except TimedOut as error:
            raise ModelError(str(error)) from None
        except Unreachable as error:
            raise ModelDown(f"Ollama is not answering at {base} ({error})") from None
    raise ModelError("the model kept refusing the request")


def _openai(llm, system, user, think, schema, max_tokens):
    base = llm["base_url"].rstrip("/")
    payload = {
        "model": llm["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": llm.get("temperature", 0.3),
        "max_tokens": max_tokens,
    }
    if schema is not None:
        payload["response_format"] = {"type": "json_object"}
    if isinstance(think, str):
        payload["reasoning_effort"] = think
    headers = {"Authorization": "Bearer " + (llm.get("api_key") or "none")}
    for attempt in range(4):
        try:
            answer = post_json(base + "/chat/completions", payload, headers, timeout=llm.get("timeout_seconds", 900))
            return answer["choices"][0]["message"].get("content") or ""
        except HTTPError as error:
            text = str(error).lower()
            if "response_format" in payload and "response_format" in text:
                payload.pop("response_format")
                continue
            if "reasoning_effort" in payload and "reasoning" in text:
                payload.pop("reasoning_effort")
                continue
            if error.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(20)
                continue
            raise ModelError(str(error)) from None
        except TimedOut as error:
            raise ModelError(str(error)) from None
        except Unreachable as error:
            raise ModelDown(f"the model server is not answering at {base} ({error})") from None
    raise ModelError("the model kept refusing the request")


def strip_thinking(text):
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    elif text.lstrip().startswith("<think>"):
        return ""  # ran out of tokens while still thinking
    return text.strip()


def extract_json(text):
    text = strip_thinking(text or "")
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    for candidate in (text, text[text.find("{"):text.rfind("}") + 1] if "{" in text else ""):
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def ask_json(llm, system, user, schema, think=None, max_tokens=2000):
    """Ask for a JSON object. Tries a second time without the strict format if the first answer is broken."""
    obj = extract_json(chat(llm, system, user, think, schema, max_tokens))
    if obj is None:
        reminder = "\n\nReply with one valid JSON object only, no other text."
        obj = extract_json(chat(llm, system, user + reminder, think, None, max_tokens))
    return obj


def ask_text(llm, system, user, think=None, max_tokens=6000):
    return strip_thinking(chat(llm, system, user, think, None, max_tokens))
