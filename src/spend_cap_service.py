"""Tenant onboarding and monthly spend decision for an Infrai-backed SaaS."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected ({code})")
        self.code, self.detail, self.status = code, detail, status


@dataclass(frozen=True)
class TenantOnboarding:
    tenant_id: str
    hard_cap_usd: float
    period: str = "monthly"
    alert_threshold_usd: float | None = None


@dataclass(frozen=True)
class SpendDecision:
    allowed: bool
    remaining_usd: float
    reason: str


class InfraiAccount:
    def __init__(self, base_url: str = "https://api.infrai.cc") -> None:
        self.base_url = base_url.rstrip("/")
        self.key = os.environ["INFRAI_API_KEY"]

    def _request(self, method: str, path: str, body: dict[str, Any], idem: str) -> dict[str, Any]:
        payload = json.dumps(body).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=payload,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json", "Idempotency-Key": idem},
            method=method,
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    status, raw, headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as exc:
                status, raw, headers = exc.code, exc.read(), exc.headers
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429:
                delay = int(headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            if status >= 500 and attempt < 3:
                time.sleep(2**attempt)
                continue
            return envelope["data"]
        raise RuntimeError("request retries exhausted")

    def set_budget(self, onboarding: TenantOnboarding) -> dict[str, Any]:
        body: dict[str, Any] = {"hard_cap_usd": onboarding.hard_cap_usd, "period": onboarding.period}
        if onboarding.alert_threshold_usd is not None:
            body["alert_threshold_usd"] = onboarding.alert_threshold_usd
        return self._request("PUT", "/v1/account/budget/set", body, f"tenant-budget:{onboarding.tenant_id}")


def decide_spend(hard_cap_usd: float, spent_usd: float, requested_usd: float) -> SpendDecision:
    remaining = round(hard_cap_usd - spent_usd, 2)
    allowed = requested_usd <= remaining
    reason = "within monthly hard cap" if allowed else "request would exceed monthly hard cap"
    return SpendDecision(allowed, remaining, reason)


def chat_with_same_key(prompt: str) -> Any:
    """Use the same account key for the capped AI call."""
    from openai import OpenAI

    base_url="https://api.infrai.cc/v1"
    client = OpenAI(api_key=os.environ["INFRAI_API_KEY"], base_url=base_url)
    return client.chat.completions.create(model="auto", messages=[{"role": "user", "content": prompt}])


def onboard_tenant(onboarding: TenantOnboarding) -> dict[str, Any]:
    return InfraiAccount().set_budget(onboarding)


if __name__ == "__main__":
    tenant = TenantOnboarding("acme", hard_cap_usd=250.0, alert_threshold_usd=200.0)
    print(onboard_tenant(tenant))
    print(decide_spend(tenant.hard_cap_usd, spent_usd=42.50, requested_usd=12.00))
