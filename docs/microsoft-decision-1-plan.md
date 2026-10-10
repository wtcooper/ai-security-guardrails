# Plan: Microsoft-Decision-1 as a hosted decision API

**Status:** planned (2026-10-10). Waiting for an Azure subscription, or for OpenRouter access.

**What it is:**
- Microsoft's hosted decision model, launched 2026-10-09: a post-trained Qwen3.5-9B (the same base family as
  Kev-9B and Clef-flash).
- Like Jev, it takes a situation and typed questions (yes/no, choice, rating, rubric) and returns a calibrated
  probability per option. It doesn't generate text.
- **No open weights.** It runs only as a hosted service: in Microsoft Foundry now (public preview), with
  OpenRouter announced as "coming soon".

**Why it's worth testing:**
- **Same protocol as Jev.** A Foundry resource serves it on the same System One protocol Jev uses, so our tuned
  question set and adapter apply almost unchanged. That makes it a direct, like-for-like comparison with
  `jev-base`.
- **Security tested by Microsoft.** Microsoft says it tested it on 5,250 requests across 11 benchmarks covering
  harmful content, jailbreaks and prompt injection. It lists agent controls and safety screening as uses.

## Is it a cloud-agnostic API?

Yes, the same way the Azure AI Content Safety resource is: a key-authenticated HTTPS endpoint that any code can
call from anywhere. You need an Azure subscription to own the resource. Through OpenRouter, once it's listed, it
wouldn't need Azure at all; we already have an OpenRouter key.

| | Detail | Source |
|---|---|---|
| Endpoint | `POST https://<resource>.services.ai.azure.com/providers/microsoft/v1/systemone` | Third-party integrations ([everruns](https://github.com/everruns/everruns/pull/4441), [Phaseo](https://github.com/phaseoteam/Phaseo/pull/2817)); confirm with the deployment's "View code" sample |
| Auth | `api-key: <key>` header (Entra ID also supported) | Same |
| Request | `{"model": "<deployment>", "state": {...}, "questions": {...}}` (System One, as Jev) | Same; Microsoft's sample shows `state`, `questions`, `type: choice`, `criteria` |
| Deployment types | US Data Zone and EU Data Zone | Foundry catalog |
| Limits | 32,768 input tokens, text only | Catalog, via third parties |
| Price | $0.042 per million input tokens; output free (the same as Jev) | [Microsoft](https://commandline.microsoft.com/microsoft-decision-1-model-foundry/) |
| Latency | p50 85 ms, p95 125 ms in Microsoft's setup; one independent test measured a 459 ms median | Vendor; [semantic-decision-lab](https://github.com/serevy/semantic-decision-lab/issues/148) |

**Cost for us:** each of our checks is about 3,000 tokens (the tuned questions include policy text). That's about
$0.13 per 1,000 checks, or about $0.25 for a full run of both held-out test sets.

## What you need to do (Azure route)

1. **Subscription:** a pay-as-you-go Azure subscription (personal is fine).
2. **Foundry resource:** at [ai.azure.com](https://ai.azure.com), create a project. It creates the resource, in a
   region inside the US Data Zone.
3. **Deploy:** Models catalog → Microsoft-Decision-1 → Deploy, with deployment type Data Zone Standard (US). Give it
   a small tokens-per-minute quota. A full run needs about 6 million tokens.
4. **Endpoint and key:** from the resource's "Keys and Endpoint", add them to `.env` (gitignored):
   `AZURE_FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com`, `AZURE_FOUNDRY_API_KEY=...`, and the
   deployment name.
5. **Check the path:** the deployment page's "View code" sample confirms whether the System One path above is
   the one to use.

**OpenRouter route:** none of the above. When it's listed, we add a registry entry with its OpenRouter model ID.

## What we build

- **Adapter:** a small option in the Jev adapter (`src/guardlab/adapters/jev.py`) to send the key as an `api-key`
  header instead of `Authorization: Bearer`. Deferred until we have access: editing that file changes `jev-base`'s
  version ID, which would make its fresh results not count as current.
- **Registry entry:** `ms-decision-1`, with `base_url: ${AZURE_FOUNDRY_ENDPOINT}`,
  `path: /providers/microsoft/v1/systemone`, the deployment as `model`, and the same `tuned.yaml` questions and
  thresholds as `jev-base`.
- **Run:** `uv run python evals/lab/experiments/held_out.py --run ms-decision-1`, then add it to the README
  comparison under hosted decision APIs, next to Jev.

**Caveats:**
- It's in preview, so the API may change.
- The model card rules out sole automated decisions about people, which doesn't apply to security screening.
- Data stays within the chosen Data Zone.
