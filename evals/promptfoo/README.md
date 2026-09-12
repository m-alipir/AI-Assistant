# Manual Promptfoo provider evaluation

This is an optional, manual-only complement to the normal offline pytest quality gate. It contains
five synthetic cases and one provider, so a run is bounded to five model requests and 300 generated
tokens per request. It has no Gmail, production history, live feed, credential, or user data.

Before a run, an operator must explicitly approve all of the following:

1. A disposable, separately scoped OpenRouter key in `PROMPTFOO_OPENROUTER_API_KEY`.
2. A model ID in `PROMPTFOO_MODEL_ID` that has been deliberately selected from the versioned model
   configuration, plus a budget covering at most five requests with 300 output tokens each.
3. A trusted local Promptfoo installation and the committed configuration below. Do not add
   JavaScript assertions, custom providers, transforms, red-team generators, or unreviewed files.

The normal application, scheduler, Gmail, YouTube, and RSSHub pilot must remain stopped for this
manual run. Promptfoo must not inherit `OPENROUTER_API_KEY`; use only the separate variable above.

```powershell
$env:PROMPTFOO_OPENROUTER_API_KEY = "separately-scoped-key"
$env:PROMPTFOO_MODEL_ID = "approved/provider-model"
promptfoo eval -c evals/promptfoo/promptfooconfig.yaml --no-cache
```

Do not use Promptfoo sharing or upload a report. Delete any local result artifact after reviewing
it. A failed assertion is an evaluation result, not authorization to change prompts/models; record
the outcome and obtain explicit approval for any configuration change.
