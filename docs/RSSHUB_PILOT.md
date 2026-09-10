# RSSHub credential-free pilot

## Scope and safety boundary

This is an explicit seven-day local experiment, not a normal application source configuration.
`compose.rsshub-pilot.yaml` has no effect unless the `rsshub-pilot` profile is selected. It keeps
the regular `app` service out of that profile, so existing RSS and YouTube sources, Gmail, the
scheduler, and all OpenRouter calls remain off. RSSHub uses its in-memory cache only; there is no
credential, Redis, Puppeteer, or browserless dependency.

The pilot runner stores aggregate route measurements only. It never stores feed entry text, URLs,
or article bodies. `retained_items` means fresh, de-duplicated feed candidates; it does not mean
LLM-validated knowledge events.

## Approved routes

The paths below were checked against the current RSSHub provider manifest on 2026-09-10. All are
credential-free and declare no Puppeteer requirement. "Upstream maintained" means that RSSHub
has a provider implementation; the pilot still decides operational fitness.

| Source | Route path | Example route URL | Stream / tier | Why | Maintenance / known risk |
| --- | --- | --- | --- | --- | --- |
| Hacker News Best | `/hackernews/best/sources` | `http://rsshub:1200/hackernews/best/sources` | tech / community_discovery | high-signal developer discussion | upstream maintained; community discovery is not verified news |
| Hacker News Newest | `/hackernews/newest/sources` | `http://rsshub:1200/hackernews/newest/sources` | tech / community_discovery | early software and AI signals | upstream maintained; high noise and duplicates |
| Hacker News Ask | `/hackernews/ask/sources` | `http://rsshub:1200/hackernews/ask/sources` | personalized / community_discovery | practitioner questions and tools | upstream maintained; opinion-led content |
| Hacker News Show | `/hackernews/show/sources` | `http://rsshub:1200/hackernews/show/sources` | tech / community_discovery | new projects and open-source launches | upstream maintained; self-promotion risk |
| Hacker News Jobs | `/hackernews/jobs/sources` | `http://rsshub:1200/hackernews/jobs/sources` | tech / community_discovery | ecosystem demand signal | upstream maintained; low briefing relevance possible |
| Hacker News Front | `/hackernews/front/sources` | `http://rsshub:1200/hackernews/front/sources` | tech / community_discovery | general top technical discussion | upstream maintained; overlaps other HN views |
| The Verge Apps | `/theverge/apps` | `http://rsshub:1200/theverge/apps` | tech / major_publication | software platform coverage | upstream maintained; editorial overlap |
| The Verge Android | `/theverge/android` | `http://rsshub:1200/theverge/android` | tech / major_publication | mobile platform developments | upstream maintained; vendor-news skew |
| The Verge Microsoft | `/theverge/microsoft` | `http://rsshub:1200/theverge/microsoft` | tech / major_publication | Windows, cloud, and AI platform changes | upstream maintained; vendor-news skew |
| The Verge Web | `/theverge/web` | `http://rsshub:1200/theverge/web` | tech / major_publication | web platform and browser developments | upstream maintained; editorial overlap |
| The Verge Gaming | `/theverge/gaming` | `http://rsshub:1200/theverge/gaming` | personalized / major_publication | game development ecosystem | upstream maintained; consumer-game focus |
| The Verge Policy | `/theverge/policy` | `http://rsshub:1200/theverge/policy` | tech / major_publication | technology regulation and security policy | upstream maintained; policy reporting is time-sensitive |
| AP Top News | `/apnews/topics/apf-topnews` | `http://rsshub:1200/apnews/topics/apf-topnews` | world / wire_service | reliable world-news baseline | upstream maintained; direct BBC/world feeds remain primary |
| Apple Security Releases | `/apple/security-releases/en-us` | `http://rsshub:1200/apple/security-releases/en-us` | tech / official_vendor | first-party vulnerability updates | upstream maintained; vendor scope only |
| Epic Free Games | `/epicgames/freegames/en-US/US` | `http://rsshub:1200/epicgames/freegames/en-US/US` | personalized / official_vendor | game ecosystem discovery | upstream maintained; promotion rather than news |

GitHub Trending is `needs-auth/deferred`: its current RSSHub provider declares
`GITHUB_ACCESS_TOKEN`. No token will be requested or created. Current RSSHub has no Reddit
provider namespace; direct Reddit RSS remains a separate backlog decision and, if approved, must
use `community/discovery` only.

## Run and evaluate

Start a single daily observation explicitly; it runs once and exits:

```powershell
docker compose -f compose.yaml -f compose.rsshub-pilot.yaml --profile rsshub-pilot run --rm rsshub-pilot-runner
```

Run that command once per day for seven days. It applies the pilot aggregate-only migration before
collecting. It does not enable the scheduler. Record RSSHub memory alongside each run from the
host, because the pilot intentionally has no Docker socket access:

```powershell
docker stats --no-stream aipersonalassistant-rsshub-1
```

After day seven, query the persisted per-route aggregates and choose exactly one outcome for each
route: `keep`, `disable`, or `needs-auth`. Review availability, latency, freshness
(`fresh_items / fetched_items`), duplicate rate, daily retained candidates, error rate, and the
seven recorded RSSHub memory samples. Do not promote a community/discovery source to verified news
without independent corroboration.

The following read-only report returns the aggregate-only overall and per-route seven-day window;
it does not fetch a source:

```powershell
docker compose -f compose.yaml -f compose.rsshub-pilot.yaml --profile rsshub-pilot run --rm --no-deps --build --entrypoint python rsshub-pilot-runner -m app.pilot.rsshub --report-days 7
```
