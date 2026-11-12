"""Telegram messages: progress updates and the final report. Optional: without a bot it just logs."""

import json
import os
import uuid

from common import HTTPError, Unreachable, http_request, log, post_json

TELEGRAM = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org") + "/bot{token}/{method}"


def telegram(token, method, **params):
    answer = post_json(TELEGRAM.format(token=token, method=method), params, timeout=params.get("timeout", 0) + 30)
    if not answer.get("ok"):
        raise RuntimeError(answer.get("description", "Telegram returned an error"))
    return answer["result"]


def send_document(token, chat_id, path, caption=""):
    boundary = "----researcher" + uuid.uuid4().hex
    fields = {"chat_id": str(chat_id), "caption": caption[:1000]}
    body = b""
    for name, value in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode("utf-8")
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{path.name}\"\r\n"
             f"Content-Type: text/markdown\r\n\r\n").encode("utf-8")
    body += path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    raw, _, _ = http_request(TELEGRAM.format(token=token, method="sendDocument"), data=body, timeout=120,
                             headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    answer = json.loads(raw.decode("utf-8"))
    if not answer.get("ok"):
        raise RuntimeError(answer.get("description", "Telegram returned an error"))


def split_message(text, limit=3900):
    """Telegram allows 4096 characters per message; split on paragraph breaks."""
    parts, current = [], ""
    for paragraph in text.split("\n\n"):
        while len(paragraph) > limit:
            parts.append(paragraph[:limit])
            paragraph = paragraph[limit:]
        if len(current) + len(paragraph) + 2 > limit and current:
            parts.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        parts.append(current)
    return parts


class Notifier:
    def __init__(self, secrets, quiet=False):
        settings = secrets.get("telegram") or {}
        self.token = settings.get("token") or ""
        self.chat_id = settings.get("chat_id")
        self.enabled = bool(self.token and self.chat_id) and not quiet

    def send(self, text):
        log.info("Message: %s", text.replace("\n", " | ")[:300])
        if not self.enabled:
            return
        for part in split_message(text):
            try:
                telegram(self.token, "sendMessage", chat_id=self.chat_id, text=part,
                         link_preview_options={"is_disabled": True})
            except (RuntimeError, HTTPError, Unreachable) as error:
                log.info("  (Telegram message failed: %s)", error)

    def send_file(self, path, caption=""):
        if not self.enabled or not path.exists():
            return
        try:
            send_document(self.token, self.chat_id, path, caption)
        except (RuntimeError, HTTPError, Unreachable) as error:
            log.info("  (Telegram file upload failed: %s)", error)
