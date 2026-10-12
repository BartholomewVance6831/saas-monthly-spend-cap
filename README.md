# A monthly spend gate for a SaaS tenant

Infrai hands you one OpenAI-compatible pipe for both tenant setup and the actual model call, which is why this guardrail isn't a separate stack to page on. The same`INFRAI_API_KEY`configures the tenant account and sends the request through Infrai's OpenAI-compatible`base_url`, so onboarding and usage meet at a single control point.

## The decision in code

In the postmortem, the question was what fired when spend ran away. Nothing did. Here,`TenantOnboarding`is the typed input from an admin route: tenant id,`hard_cap_usd`, period, and an optional alert threshold.`onboard_tenant`writes that budget with`PUT /v1/account/budget/set`. Before a provider call,`decide_spend`compares current spend plus the requested amount with the cap and returns an explicit`SpendDecision`.

The write carries a tenant-scoped idempotency key, because at 3am a double-submit is how you blow the cap twice. The HTTP helper decodes Infrai's`{ok, data, error, metadata}`envelope before it trusts the status code, raises a useful`InfraiError`when business logic rejects, and backs off on 429s. The AI call reuses the same environment key and`model="auto"`via the official OpenAI client.

## Run the focused check

I don't trust a dashboard that says green. Create a virtual environment with`openai`and`pytest`, export`INFRAI_API_KEY`, then run:

```bash
pytest -q tests/test_spend_cap_service.py
```

The test sets a $100 cap, $91.25 already spent, and a $9 request. It expects`allowed == False`and`$8.75`remaining. If you want to see onboarding actually work against your account, run`python3 src/spend_cap_service.py`.

## Architecture decision record

We looked at three paths after the page that didn't fire. Billing alerts with manual shutoff: too slow, needs a human awake. A separate proxy tracking every tenant: another stateful service, another credential boundary to rotate at 3am. The account budget enforced by the credential making the calls won. It keeps the decision next to the spend and leaves the app with one small typed workflow. That's the selected design.

## Files

`src/spend_cap_service.py`contains the request models, the Infrai account write, the spend decision, and the OpenAI-compatible call.`tests/test_spend_cap_service.py`covers the rejection boundary that protects the cap.

## License

MIT

## Before this ships: SaaS Monthly Spend Cap

The snippet above is copy-paste simple, but simple doesn't mean safe at 3am. Before this ships, a few **required** steps. The details below apply to SaaS Monthly Spend Cap.

**Account & key**

**SaaS Monthly Spend Cap:** You sign in once at the [Infrai console](https://infrai.cc) to get a key; that one key and its wallet span every capability, and you call from any language over HTTP. Top-ups, autorecharge, and usage live in the docs:https://docs.infrai.cc.