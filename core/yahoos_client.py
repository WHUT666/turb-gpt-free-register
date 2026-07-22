# -*- coding: utf-8 -*-
"""yahoos.nl 临时邮箱客户端。

API（Session 绑定）：
  GET api.php?action=set_email&email=xxx@yahoos.nl
  GET api.php?action=check
  GET api.php?action=read&id=<id>
  GET api.php?action=new

默认用 faker 英文名 + 4 位数字创建本地部分，再 set_email 绑定。
"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field

import requests
from faker import Faker

from config import email as _email_cfg
from core.otp_utils import extract_otp, looks_like_openai_email

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://yahoos.nl"
DEFAULT_DOMAIN = "yahoos.nl"
REQUEST_TIMEOUT = 20
_FAKER = Faker("en_US")
_LOCAL_RE = re.compile(r"^[a-z][a-z0-9]{2,31}$")


class YahoosError(RuntimeError):
    """yahoos.nl 服务请求或邮箱取码失败。"""


@dataclass
class YahoosAccount:
    email: str
    session: requests.Session = field(repr=False)


_CONTEXT_CACHE: dict[str, YahoosAccount] = {}


def _cache_key(email: str) -> str:
    return str(email or "").strip().lower()


def _base_url() -> str:
    base = str(getattr(_email_cfg, "YAHOOS_API_BASE", "") or DEFAULT_BASE_URL).strip().rstrip("/")
    return base or DEFAULT_BASE_URL


def _new_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    return session


def _api(session: requests.Session, action: str, **params):
    params = {"action": action, **params}
    try:
        resp = session.get(_base_url() + "/api.php", params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise YahoosError(f"yahoos.nl 请求失败 ({action}): {type(exc).__name__}: {exc}") from exc
    if resp.status_code >= 400:
        raise YahoosError(f"yahoos.nl 请求失败 ({action}): HTTP {resp.status_code}; {resp.text[:200]}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise YahoosError(f"yahoos.nl 响应不是 JSON ({action}): {resp.text[:200]}") from exc
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise YahoosError(f"yahoos.nl 请求失败 ({action}): {payload}")
    return payload


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


def _domain() -> str:
    domain = str(getattr(_email_cfg, "YAHOOS_DOMAIN", "") or DEFAULT_DOMAIN).strip().lstrip("@").lower()
    return domain or DEFAULT_DOMAIN


def bind_email(email: str) -> YahoosAccount:
    """绑定指定 yahoos.nl 邮箱并缓存 Session。"""
    target = str(email or "").strip()
    if not target or "@" not in target:
        raise YahoosError("yahoos.nl 邮箱地址无效")
    session = _new_session()
    # 先打开首页拿 PHPSESSID
    try:
        session.get(_base_url() + "/", timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass
    data = _api(session, "set_email", email=target)
    bound = str(data.get("email") or target).strip()
    account = YahoosAccount(email=bound, session=session)
    _CONTEXT_CACHE[_cache_key(bound)] = account
    logger.info("[yahoos.nl] 已绑定邮箱: %s", bound)
    return account


def pick_account(email: str | None = None) -> YahoosAccount:
    """领取邮箱：固定地址优先；否则 faker 英文名+4位数字创建并绑定。"""
    if email:
        return bind_email(email)

    last_error: Exception | None = None
    for attempt in range(1, 6):
        local = generate_local_part()
        candidate = f"{local}@{_domain()}"
        try:
            account = bind_email(candidate)
            logger.info(
                "[yahoos.nl] 已创建临时邮箱: %s (faker local=%s, attempt=%s)",
                account.email,
                local,
                attempt,
            )
            return account
        except YahoosError as exc:
            last_error = exc
            logger.warning("[yahoos.nl] 创建失败 local=%s: %s", local, exc)

    logger.warning("[yahoos.nl] faker 自定义创建连续失败，回退 action=new: %s", last_error)
    session = _new_session()
    try:
        session.get(_base_url() + "/", timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass
    data = _api(session, "new")
    bound = str(data.get("email") or "").strip()
    if not bound or "@" not in bound:
        raise YahoosError(f"yahoos.nl 生成邮箱失败: {data}")
    account = YahoosAccount(email=bound, session=session)
    _CONTEXT_CACHE[_cache_key(bound)] = account
    logger.info("[yahoos.nl] 已回退生成临时邮箱: %s", bound)
    return account


def get_account_context(email: str) -> YahoosAccount | None:
    return _CONTEXT_CACHE.get(_cache_key(email))


def release_account(email: str, status: str = "available", note: str | None = None) -> None:
    _CONTEXT_CACHE.pop(_cache_key(email), None)
    logger.info("[yahoos.nl] 已释放邮箱: %s（status=%s, note=%s）", email, status, note or "")


def _otp_item(item: dict) -> dict:
    # 注意：列表接口里的 otp 字段不可信（会把 CSS 颜色 #202123 当成验证码）。
    # 只从正文/主题抽取，不使用 item["otp"]。
    return {
        "id": item.get("id"),
        "from": item.get("from") or item.get("from_address") or item.get("sender") or "",
        "fromName": item.get("from_name") or item.get("fromName") or "",
        "subject": item.get("subject") or "",
        "text": item.get("body_text") or item.get("body_preview") or item.get("body") or item.get("content") or "",
        "html": item.get("body_html") or item.get("html") or item.get("body") or "",
        "date": item.get("date") or item.get("time") or item.get("received") or item.get("timestamp"),
    }


def _message_ts(item: dict) -> float | None:
    raw = item.get("date")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    # 毫秒时间戳兜底
    if value > 1e12:
        value /= 1000.0
    return value


def _read_mail(account: YahoosAccount, mail_id) -> dict:
    detail = _api(account.session, "read", id=mail_id)
    if not isinstance(detail, dict):
        return {}
    for key in ("email", "data", "message"):
        nested = detail.get(key)
        if isinstance(nested, dict):
            return nested
    return detail


def _ensure_account(email: str) -> YahoosAccount:
    cached = get_account_context(email)
    if cached:
        return cached
    return bind_email(email)


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    target = str(email or "").strip()
    if not target:
        raise YahoosError("yahoos.nl 取码缺少邮箱地址")
    account = _ensure_account(target)
    wait_seconds = int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT)
    interval = max(1, int(poll_interval if poll_interval is not None else _email_cfg.OTP_POLL_INTERVAL))
    settle = max(0, int(settle_seconds if settle_seconds is not None else _email_cfg.OTP_SETTLE_SECONDS))
    deadline = time.monotonic() + max(0, wait_seconds)
    best_otp: str | None = None
    best_ts: float = -1.0
    settle_until: float | None = None
    last_error = "收件箱为空或尚未出现新的 OpenAI 验证码"
    after = float(after_ts) - 30 if after_ts is not None else None

    logger.info("[yahoos.nl] 开始轮询邮箱 %s，最长 %ss", target, wait_seconds)
    while time.monotonic() <= deadline:
        try:
            data = _api(account.session, "check")
            emails = data.get("emails") if isinstance(data.get("emails"), list) else []
            # 优先读最新邮件
            ranked = sorted(
                (s for s in emails if isinstance(s, dict)),
                key=lambda s: float(s.get("date") or 0),
                reverse=True,
            )
            for summary in ranked:
                summary_item = _otp_item(summary)
                msg_ts = _message_ts(summary_item)
                if after is not None and msg_ts is not None and msg_ts < after:
                    continue
                if not looks_like_openai_email(summary_item) and "openai" not in str(summary.get("from") or "").lower():
                    continue
                mail_id = summary.get("id")
                if mail_id is None:
                    continue
                detail_mail = _read_mail(account, mail_id)
                detail_item = _otp_item(detail_mail)
                if after is not None:
                    detail_ts = _message_ts(detail_item) or msg_ts
                    if detail_ts is not None and detail_ts < after:
                        continue
                otp = extract_otp(detail_item) or extract_otp(summary_item) or ""
                if not (otp and otp.isdigit() and 4 <= len(otp) <= 8):
                    continue
                candidate_ts = _message_ts(detail_item) or msg_ts or 0.0
                if candidate_ts >= best_ts and otp != best_otp:
                    best_otp = otp
                    best_ts = float(candidate_ts)
                    settle_until = time.monotonic() + settle
                    logger.info("[yahoos.nl] 锁定 OTP 候选 %s（mail_id=%s），等待 %ss 确认", otp, mail_id, settle)
                    break  # 已取到最新一封，进入 settle
            if best_otp and settle_until is not None and time.monotonic() >= settle_until:
                return best_otp
        except YahoosError as exc:
            last_error = str(exc)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))

    if best_otp:
        return best_otp
    raise YahoosError(f"等待 yahoos.nl 验证码超时: {target}; {last_error}")
