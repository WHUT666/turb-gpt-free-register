# -*- coding: utf-8 -*-
"""ChatGPT 账号套餐/试用资格查询。"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

from core.session import BrowserSession

logger = logging.getLogger(__name__)

ACCOUNTS_CHECK_PATH = "/backend-api/accounts/check/v4-2023-04-27"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_token(token: str) -> str:
    token = (token or "").strip().strip('"').strip("'")
    if token.lower().startswith("authorization:"):
        token = token.split(":", 1)[1].strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def decode_jwt_payload_unverified(token: str) -> dict:
    """仅本地解析 JWT payload，不校验签名。"""
    token = normalize_token(token)
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception:
        return {}


def token_claims(token: str) -> dict:
    payload = decode_jwt_payload_unverified(token)
    auth = payload.get("https://api.openai.com/auth") or {}
    profile = payload.get("https://api.openai.com/profile") or {}
    exp = payload.get("exp")
    exp_iso = None
    expired = None
    if isinstance(exp, (int, float)):
        exp_iso = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        expired = datetime.now(tz=timezone.utc).timestamp() >= float(exp)
    return {
        "payload": payload,
        "email": profile.get("email"),
        "user_name": profile.get("name"),
        "user_id": auth.get("chatgpt_user_id") or auth.get("user_id"),
        "account_id": auth.get("chatgpt_account_id"),
        "claim_plan_type": auth.get("chatgpt_plan_type"),
        "exp": exp,
        "token_expires_at": exp_iso,
        "token_expired": expired,
    }


def _common_headers(env: BrowserSession, token: str) -> dict[str, str]:
    headers = env._get_common_headers()
    headers.update({
        "accept": "*/*",
        "authorization": f"Bearer {normalize_token(token)}",
        "oai-device-id": env.device_id,
        "oai-language": env.navigator_language(),
        "referer": "https://chatgpt.com/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-openai-target-path": ACCOUNTS_CHECK_PATH,
        "x-openai-target-route": ACCOUNTS_CHECK_PATH,
    })
    return headers


def parse_accounts_check(data: dict, *, token: str = "") -> dict:
    """从 accounts/check 响应提取套餐和 Plus 试用资格。"""
    claims = token_claims(token) if token else {}
    claim_account_id = claims.get("account_id")
    accounts = data.get("accounts") if isinstance(data, dict) else None
    if not isinstance(accounts, dict):
        raise ValueError("响应缺少 accounts 对象")

    item = None
    account_key = None
    if claim_account_id and isinstance(accounts.get(claim_account_id), dict):
        item = accounts.get(claim_account_id)
        account_key = claim_account_id
    elif isinstance(accounts.get("default"), dict):
        item = accounts.get("default")
        account = item.get("account") or {}
        account_key = account.get("account_id") or "default"
    else:
        for k, v in accounts.items():
            if k != "default" and isinstance(v, dict):
                item = v
                account_key = k
                break
    if not isinstance(item, dict):
        raise ValueError("未找到可解析的账号条目")

    account = item.get("account") or {}
    entitlement = item.get("entitlement") or {}
    last_sub = item.get("last_active_subscription") or {}
    eligible_promo_campaigns = item.get("eligible_promo_campaigns") or {}
    plus_campaign = eligible_promo_campaigns.get("plus") if isinstance(eligible_promo_campaigns, dict) else None
    plus_meta = (plus_campaign or {}).get("metadata") or {}
    discount = plus_meta.get("discount") or {}
    duration = plus_meta.get("duration") or {}

    plan_type = account.get("plan_type") or claims.get("claim_plan_type") or ""
    subscription_plan = entitlement.get("subscription_plan") or ""
    has_active_subscription = bool(entitlement.get("has_active_subscription"))
    is_free = str(plan_type).lower() == "free" or str(subscription_plan).lower() == "chatgptfreeplan"
    plus_trial_eligible = bool(is_free and plus_campaign)

    offers = ((item.get("eligible_offers") or {}).get("offers") or [])
    eligible_offer_ids = [o.get("id") for o in offers if isinstance(o, dict) and o.get("id")]

    result = {
        "ok": True,
        "checked_at": now_iso(),
        "account_id": account.get("account_id") or account_key or claim_account_id,
        "account_user_role": account.get("account_user_role"),
        "current_plan_type": plan_type,
        "subscription_plan": subscription_plan,
        "has_active_subscription": has_active_subscription,
        "is_active_subscription_gratis": bool(entitlement.get("is_active_subscription_gratis")),
        "expires_at": entitlement.get("expires_at"),
        "renews_at": entitlement.get("renews_at"),
        "cancels_at": entitlement.get("cancels_at"),
        "billing_period": entitlement.get("billing_period"),
        "billing_currency": entitlement.get("billing_currency"),
        "is_delinquent": bool(entitlement.get("is_delinquent")),
        "discount_type": (entitlement.get("discount") or {}).get("discount_type"),
        "discount_amount": (entitlement.get("discount") or {}).get("amount"),
        "discount_duration_num_periods": (entitlement.get("discount") or {}).get("duration_num_periods"),
        "discount_expires_at": (entitlement.get("discount") or {}).get("discount_expires_at"),
        "discount_cancellation_policy": (entitlement.get("discount") or {}).get("cancellation_policy"),
        "discount_promo_campaign_id": (entitlement.get("discount") or {}).get("promo_campaign_id"),
        "last_purchase_origin_platform": last_sub.get("purchase_origin_platform"),
        "last_will_renew": bool(last_sub.get("will_renew")),
        "plus_trial_eligible": plus_trial_eligible,
        "plus_trial_campaign_id": (plus_campaign or {}).get("id"),
        "plus_trial_title": plus_meta.get("title"),
        "plus_trial_summary": plus_meta.get("summary"),
        "plus_trial_discount_percentage": discount.get("percentage"),
        "plus_trial_duration_num_periods": duration.get("num_periods"),
        "plus_trial_duration_period": duration.get("period"),
        "plus_trial_promotion_type_label": plus_meta.get("promotion_type_label"),
        "eligible_offer_ids": eligible_offer_ids,
        "features_count": len(item.get("features") or []),
        "can_access_with_session": bool(item.get("can_access_with_session")),
        "raw_account_plan_type": account.get("plan_type"),
    }
    result.update({k: v for k, v in claims.items() if k != "payload" and v is not None})
    return result


def check_account_plan(token: str, *, proxy: Optional[str] = None, timezone_offset_min: str = "-") -> dict:
    token = normalize_token(token)
    if not token:
        return {"ok": False, "checked_at": now_iso(), "error": "token 为空"}
    claims = token_claims(token)
    if claims.get("token_expired") is True:
        return {
            "ok": False,
            "checked_at": now_iso(),
            "http_status": None,
            "error": "token 已过期",
            **{k: v for k, v in claims.items() if k != "payload"},
        }

    url = f"https://chatgpt.com{ACCOUNTS_CHECK_PATH}?timezone_offset_min={quote(str(timezone_offset_min))}"
    env = BrowserSession(proxy=proxy)
    try:
        resp = env.session.get(url, headers=_common_headers(env, token), allow_redirects=False)
        text = resp.text or ""
        try:
            data: Any = resp.json()
        except Exception:
            data = json.loads(text) if text.strip().startswith(("{", "[")) else None
        if not (200 <= int(resp.status_code) < 300):
            return {
                "ok": False,
                "checked_at": now_iso(),
                "http_status": resp.status_code,
                "error": f"HTTP {resp.status_code}",
                "response_preview": text[:500],
                **{k: v for k, v in claims.items() if k != "payload"},
            }
        if not isinstance(data, dict):
            return {
                "ok": False,
                "checked_at": now_iso(),
                "http_status": resp.status_code,
                "error": "响应不是 JSON 对象",
                "response_preview": text[:500],
                **{k: v for k, v in claims.items() if k != "payload"},
            }
        parsed = parse_accounts_check(data, token=token)
        parsed["http_status"] = resp.status_code
        return parsed
    except Exception as exc:
        logger.debug("套餐查询失败: %s: %s", type(exc).__name__, exc, exc_info=True)
        return {
            "ok": False,
            "checked_at": now_iso(),
            "http_status": None,
            "error": f"{type(exc).__name__}: {exc}",
            **{k: v for k, v in claims.items() if k != "payload"},
        }
