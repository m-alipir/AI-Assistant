# Offline quality gate

`golden_cases.yaml` contains only synthetic or public-style minimal inputs. It is checked by the
normal pytest suite for required coverage and for common secret/private-data patterns. The suite
does not call OpenRouter, Gmail, RSS, YouTube, or a remote evaluator.

Promptfoo remains an optional manual runner: its configuration, transforms, providers, and reports
are executable/trusted local inputs. Do not run it against Gmail, production history, credentials,
or unreviewed fixture files. The committed manual-only configuration in `evals/promptfoo/` uses a
separate scoped key, explicit five-request/300-token bound, sanitized source text, and no sharing.

RSSHub is not enabled by this milestone slice. It needs an operator-approved allow-list of 10–20
routes and a separate Compose profile; public instances, arbitrary routes, and private-network
targets are not acceptable defaults.
