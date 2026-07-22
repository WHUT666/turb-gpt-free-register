# -*- coding: utf-8 -*-
"""outlook.tw 临时邮箱客户端。

匿名 API（无需 Key）：
  GET  /api/domains
  POST /api/create  {local, domainIndex}   -> {email, expires, anonymous}
  GET  /api/generate?length=8&domainIndex=0  -> 兜底随机邮箱
  GET  /api/emails?mailbox=<email>
  GET  /api/email/<id>
"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime

import requests
from faker import Faker

from config import email as _email_cfg
from core.otp_utils import extract_otp, looks_like_openai_email

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://outlook.tw"
REQUEST_TIMEOUT = 20
_FAKER = Faker("en_US")
_LOCAL_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class OutlookTwError(RuntimeError):
    """outlook.tw 服务请求或邮箱取码失败。"""


@dataclass
class OutlookTwAccount:
    email: str
    expires: float | None = None
    local: str | None = None


_CONTEXT_CACHE: dict[str, OutlookTwAccount] = {}


def _cache_key(email: str) -> str:
    return str(email or "").strip().lower()


def _base_url() -> str:
    base = str(getattr(_email_cfg, "OUTLOOK_TW_API_BASE", "") or DEFAULT_BASE_URL).strip().rstrip("/")
    return base or DEFAULT_BASE_URL


def _domain_index() -> int:
    return max(0, int(getattr(_email_cfg, "OUTLOOK_TW_DOMAIN_INDEX", 0) or 0))


def _session() -> requests.Session:
    """直连 outlook.tw，避免继承系统代理导致偶发 ProxyError。"""
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"Accept": "application/json"})
    return session


def _parse_expires(raw) -> float | None:
    try:
        if raw is None:
            return None
        expires = float(raw)
        if expires > 1e12:
            expires = expires / 1000.0
        return expires
    except (TypeError, ValueError):
        return None


def _request(method: str, path: str, *, params: dict | None = None, json: dict | None = None):
    url = _base_url() + path
    try:
        with _session() as session:
            resp = session.request(
                method,
                url,
                params=params,
                json=json,
                timeout=REQUEST_TIMEOUT,
            )
    except requests.RequestException as exc:
        raise OutlookTwError(f"outlook.tw 请求失败 ({path}): {type(exc).__name__}: {exc}") from exc

    if resp.status_code >= 400:
        raise OutlookTwError(f"outlook.tw 请求失败 ({path}): HTTP {resp.status_code}; {resp.text[:200]}")

    try:
        return resp.json()
    except ValueError as exc:
        raise OutlookTwError(f"outlook.tw 响应不是 JSON ({path}): HTTP {resp.status_code}") from exc


def _get(path: str, params: dict | None = None):
    return _request("GET", path, params=params)


def generate_local_part() -> str:
    """用 faker 英文名 + 随机 4 位数字生成邮箱用户名。"""
    for _ in range(20):
        first = re.sub(r"[^A-Za-z]", "", str(_FAKER.first_name() or "")).lower()
        if len(first) < 2:
            first = "user"
        first = first[:20]
        digits = f"{random.randint(0, 9999):04d}"
        local = f"{first}{digits}"
        if _LOCAL_RE.match(local):
            return local
    return f"user{random.randint(0, 9999):04d}"


def _create_mailbox(local: str) -> dict:
    return _request(
        "POST",
        "/api/create",
        json={"local": local, "domainIndex": _domain_index()},
    )


def pick_account() -> OutlookTwAccount:
    """用 faker 名字+4位数字创建 outlook.tw 邮箱并缓存。"""
    last_error: Exception | None = None
    for attempt in range(1, 6):
        local = generate_local_part()
        try:
            data = _create_mailbox(local)
            if not isinstance(data, dict):
                raise OutlookTwError(f"outlook.tw 创建邮箱响应异常: {data!r}")
            email = str(data.get("email") or "").strip()
            if not email or "@" not in email:
                domains = _get("/api/domains")
                domain = "outlook.tw"
                if isinstance(domains, list) and domains:
                    idx = min(_domain_index(), len(domains) - 1)
                    domain = str(domains[idx] or domain)
                email = f"{local}@{domain}"
            account = OutlookTwAccount(
                email=email,
                expires=_parse_expires(data.get("expires")),
                local=local,
            )
            _CONTEXT_CACHE[_cache_key(email)] = account
            logger.info(
                "[outlook.tw] 已创建临时邮箱: %s (faker local=%s, attempt=%s)",
                email,
                local,
                attempt,
            )
            return account
        except OutlookTwError as exc:
            last_error = exc
            logger.warning("[outlook.tw] 创建失败 local=%s: %s", local, exc)
            continue

    logger.warning("[outlook.tw] faker 自定义创建连续失败，回退 /api/generate: %s", last_error)
    data = _get("/api/generate", params={"length": 8, "domainIndex": _domain_index()})
    if not isinstance(data, dict):
        raise OutlookTwError(f"outlook.tw 生成邮箱响应异常: {data!r}")
    email = str(data.get("email") or "").strip()
    if not email or "@" not in email:
        raise OutlookTwError("outlook.tw 生成邮箱响应缺少有效 email")
    account = OutlookTwAccount(email=email, expires=_parse_expires(data.get("expires")))
    _CONTEXT_CACHE[_cache_key(email)] = account
    logger.info("[outlook.tw] 已回退生成临时邮箱: %s", email)
    return account


def get_account_context(email: str) -> OutlookTwAccount | None:
    return _CONTEXT_CACHE.get(_cache_key(email))


def release_account(email: str, status: str = "available", note: str | None = None) -> None:
    _CONTEXT_CACHE.pop(_cache_key(email), None)
    logger.info("[outlook.tw] 已释放临时邮箱: %s（status=%s, note=%s）", email, status, note or "")


def _timestamp(item: dict) -> float | None:
    for key in ("received_at", "created_at", "timestamp", "date", "expires"):
        raw = item.get(key)
        if raw is None or raw == "":
            continue
        if isinstance(raw, (int, float)):
            value = float(raw)
            return value / 1000.0 if value > 1e12 else value
        text = str(raw).strip()
        if not text:
            continue
        try:
            normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
            if " " in normalized and "T" not in normalized:
                normalized = normalized.replace(" ", "T", 1)
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            continue
    return None


def _otp_item(item: dict) -> dict:
    sender = item.get("sender") or item.get("from_address") or item.get("from") or ""
    return {
        "id": item.get("id"),
        "from": sender,
        "subject": item.get("subject") or "",
        "text": item.get("content") or item.get("text") or item.get("preview") or "",
        "html": item.get("html_content") or item.get("html") or "",
        "verification_code": item.get("verification_code") or "",
    }


def _list_emails(mailbox: str) -> list[dict]:
    payload = _get("/api/emails", params={"mailbox": mailbox})
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("emails", "data", "items", "list"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise OutlookTwError(f"outlook.tw 收件箱响应格式异常: {str(payload)[:200]}")


def _email_detail(message_id: str | int) -> dict:
    detail = _get(f"/api/email/{message_id}")
    if not isinstance(detail, dict):
        raise OutlookTwError(f"outlook.tw 邮件详情响应异常: {detail!r}")
    return detail


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    """轮询 outlook.tw，返回领取时间后最新的 OpenAI 六位验证码。"""
    target = str(email or "").strip()
    if not target:
        raise OutlookTwError("outlook.tw 取码缺少邮箱地址")

    wait_seconds = int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT)
    interval = max(1, int(poll_interval if poll_interval is not None else _email_cfg.OTP_POLL_INTERVAL))
    settle = max(0, int(settle_seconds if settle_seconds is not None else _email_cfg.OTP_SETTLE_SECONDS))
    deadline = time.monotonic() + max(0, wait_seconds)
    best_otp: str | None = None
    best_timestamp = float("-inf")
    settle_until: float | None = None
    last_error = "收件箱为空或尚未出现新的 OpenAI 验证码"

    logger.info("[outlook.tw] 开始轮询邮箱 %s，最长 %ss", target, wait_seconds)
    while time.monotonic() <= deadline:
        try:
            emails = _list_emails(target)
            sortable = sorted(emails, key=lambda item: _timestamp(item) or float("-inf"), reverse=True)
            for summary in sortable:
                message_time = _timestamp(summary)
                if after_ts is not None and message_time is not None and message_time < after_ts - 30:
                    continue

                summary_item = _otp_item(summary)
                if summary_item.get("verification_code"):
                    otp = str(summary_item["verification_code"]).strip()
                    if otp.isdigit() and len(otp) == 6:
                        candidate_time = message_time if message_time is not None else float("-inf")
                        if best_otp is None or candidate_time > best_timestamp or (
                            candidate_time == best_timestamp and otp != best_otp
                        ):
                            best_otp = otp
                            best_timestamp = candidate_time
                            settle_until = time.monotonic() + settle
                            logger.info("[outlook.tw] 锁定 OTP 候选（列表），等待 %ss 确认", settle)
                        continue

                message_id = summary.get("id")
                if message_id is None or str(message_id).strip() == "":
                    otp = extract_otp(summary_item)
                    if not otp:
                        continue
                    candidate_time = message_time if message_time is not None else float("-inf")
                    if best_otp is None or candidate_time > best_timestamp or (
                        candidate_time == best_timestamp and otp != best_otp
                    ):
                        best_otp = otp
                        best_timestamp = candidate_time
                        settle_until = time.monotonic() + settle
                        logger.info("[outlook.tw] 锁定 OTP 候选（摘要），等待 %ss 确认", settle)
                    continue

                detail = _email_detail(message_id)
                detail_item = _otp_item(detail)
                if detail_item.get("verification_code"):
                    otp = str(detail_item["verification_code"]).strip()
                    if not (otp.isdigit() and len(otp) == 6):
                        otp = extract_otp(detail_item)
                else:
                    if not looks_like_openai_email(detail_item) and not looks_like_openai_email(summary_item):
                        continue
                    otp = extract_otp(detail_item) or extract_otp(summary_item)
                if not otp:
                    continue

                candidate_time = _timestamp(detail)
                candidate_time = message_time if candidate_time is None else candidate_time
                candidate_time = float("-inf") if candidate_time is None else candidate_time
                is_newer_message = candidate_time > best_timestamp
                is_updated_code = candidate_time == best_timestamp and otp != best_otp
                if best_otp is None or is_newer_message or is_updated_code:
                    best_otp = otp
                    best_timestamp = candidate_time
                    settle_until = time.monotonic() + settle
                    logger.info("[outlook.tw] 锁定 OTP 候选，等待 %ss 确认", settle)

            now = time.monotonic()
            if best_otp and settle_until is not None and now >= settle_until:
                return best_otp
        except OutlookTwError as exc:
            last_error = str(exc)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))

    if best_otp:
        return best_otp
    raise OutlookTwError(f"等待 outlook.tw 验证码超时: {target}; {last_error}")
