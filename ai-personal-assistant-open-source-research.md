# AI Personal Assistant — Open-Source Repo Research & Integration Map

**Araştırma tarihi:** 2026-09-09  
**Hedef:** Mevcut AI Personal Assistant projesini yeniden yazmadan; ingestion, web, document/RAG, sync, mobile/task app, notifications, agent tools, memory, orchestration ve observability taraflarında hazır açık kaynak projelerden maksimum leverage almak.

---

## 0. Kısa sonuç

Bu araştırmadan çıkan en değerli parçalar:

| Öncelik | Repo | Bizdeki rol | Karar |
|---|---|---|---|
| P0 | [OpenAPI Generator](https://github.com/OpenAPITools/openapi-generator) | FastAPI API → mobil/web SDK üretimi | **Hemen kullan** |
| P0 | [RSSHub](https://github.com/DIYgod/RSSHub) | RSS olmayan kaynakları feed'e çevirme | **Hemen değerlendir** |
| P0 | [Trafilatura](https://github.com/adbar/trafilatura) | HTML → temiz article + metadata | **Hemen kullan** |
| P0 | [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | YouTube transcript ingestion | **Hemen kullan** |
| P0 | [Docling](https://github.com/docling-project/docling) | PDF/DOCX/PPTX/XLSX/email → structured content | **Hemen değerlendir** |
| P0 | [ntfy](https://github.com/binwiederhier/ntfy) | Telefon/desktop push bildirim | **Own mobile app gelmeden kullan** |
| P1 | [Scrapling](https://github.com/D4Vinci/Scrapling) | Dynamic/anti-bot web scraping | **Web adapter adayı** |
| P1 | [Crawl4AI](https://github.com/unclecode/crawl4ai) | LLM-oriented crawling/Markdown | **Scrapling ile benchmark** |
| P1 | [RxDB](https://github.com/pubkey/rxdb) | Local-first/offline sync (JS/React Native) | **Mobile sync adayı** |
| P1 | [Electric](https://github.com/electric-sql/electric) | Postgres → client realtime replication | **Sync benchmark adayı** |
| P1 | [Vikunja](https://github.com/go-vikunja/vikunja) | Hazır task backend + REST + CalDAV | **Task backend alternatifi** |
| P1 | [MCP Servers](https://github.com/modelcontextprotocol/servers) | Assistant tool/connectors standardı | **Tool layer için kullan** |
| P1 | [LiteLLM](https://github.com/BerriAI/litellm) | Multi-model gateway / routing / cost | **Model sayısı artınca kullan** |
| P1 | [Langfuse](https://github.com/langfuse/langfuse) | LLM traces, latency, tokens, prompts | **Production debugging için güçlü** |
| P1 | [promptfoo](https://github.com/promptfoo/promptfoo) | Prompt/RAG/agent regression tests | **CI'a eklenebilir** |
| P2 | [Mem0](https://github.com/mem0ai/mem0) | AI memory layer | **Mevcut memory ile benchmark; kör migrate yok** |
| P2 | [LangGraph](https://github.com/langchain-ai/langgraph) | Stateful action agents | **Action-agent başlayınca** |
| P2 | [PGMQ](https://github.com/pgmq/pgmq) | Postgres-native queue | **Queue ihtiyacı doğarsa** |
| P2 | [Novu](https://github.com/novuhq/novu) | Push/email/in-app notification infra | **Multi-user app aşamasında** |
| P3 | [Pipecat](https://github.com/pipecat-ai/pipecat) | Realtime voice assistant | **Voice roadmap gelirse** |

En kritik stratejik fikir:

> **Core backend'i sökme.** Hazır repoları `adapter / service / library` olarak ekle.  
> Mevcut `PostgreSQL + pgvector + event/claim + briefing` omurgası canonical source of truth olarak kalsın.

---

# 1. Önerilen hedef mimari

```text
                           SOURCES
                              │
        ┌─────────────────────┼────────────────────────┐
        │                     │                        │
      RSS/API              YouTube                    Web
        │                     │                        │
     RSSHub          youtube-transcript-api     Scrapling/Crawl4AI
        │                     │                        │
        │                     │                  Trafilatura
        │                     │                        │
        └─────────────────────┴────────────────────────┘
                              │
                         NORMALIZATION
                              │
                       dedupe / freshness
                              │
                         event / claims
                              │
             ┌────────────────┴────────────────┐
             │                                 │
       PostgreSQL + pgvector            Doc / File ingestion
             │                           Docling/MarkItDown
             │                                 │
             └────────────────┬────────────────┘
                              │
                    Search / Ask / Memory
                              │
                     LLM Gateway (LiteLLM)
                              │
                   Daily briefing / Agent
                              │
            ┌─────────────────┼──────────────────┐
            │                 │                  │
         Mobile            Notifications       Tools/Actions
      RxDB/Electric           ntfy/Novu          MCP layer
            │                                      │
         Task App                              Gmail/Calendar/
            │                                  GitHub/etc.
       Task Service
   internal DB or Vikunja
```

---

# 2. Data ingestion / web / news

## 2.1 RSSHub

**Repo:** https://github.com/DIYgod/RSSHub  
**License:** AGPL-3.0  
**Rol:** RSS feed'i olmayan site ve platformları standard RSS'e dönüştürmek.

### Bizde neden değerli?

Mevcut `RSSSource` benzeri ingestion kodunu tekrar kullanabiliriz:

```text
Unsupported website/platform
        ↓
      RSSHub
        ↓
       RSS
        ↓
existing RSS ingestion
```

Her site için özel scraper yazmak yerine RSSHub route mevcutsa neredeyse sıfır custom code.

### Karar

**P0 / ayrı Docker service olarak değerlendir.**

Core dependency yapma. Bir source bozulursa RSSHub adapter'ı düşsün, sistemin geri kalanı çalışmaya devam etsin.

---

## 2.2 Trafilatura

**Repo:** https://github.com/adbar/trafilatura  
**License:** Apache-2.0  
**Rol:** HTML içinden actual article text + title + author + date + metadata extraction.

### Bizde neden değerli?

Scraper sayfayı getirir; Trafilatura gürültüyü temizler:

```text
HTML
 ├ navbar       ✗
 ├ cookie       ✗
 ├ related      ✗
 ├ ads          ✗
 └ article      ✓
```

LLM'e ham HTML yerine temiz article göndermek:

- token kullanımını düşürür,
- extraction kalitesini artırır,
- site-specific selector ihtiyacını azaltır.

### Karar

**P0. Web ingestion'ın default content extractor'ı olmaya çok uygun.**

---

## 2.3 youtube-transcript-api

**Repo:** https://github.com/jdepoix/youtube-transcript-api  
**Rol:** Manual ve auto-generated YouTube subtitles/transcripts almak.

API key veya full browser gerektirmeden transcript çekebilmesi bizim kullanım için güçlü.

### Kullanım

```text
YouTube video
  ↓
title / description
  +
full transcript
  ↓
LLM extraction
  ↓
events / claims / products / numbers
```

Description'ın kaçırdığı bilgileri transcript yakalar.

### Risk

YouTube'un undocumented davranışlarına bağlı olduğu için kırılabilir.  
Bu yüzden transcript başarısızsa normal metadata ingestion devam etmeli.

### Karar

**P0.**

---

## 2.4 Scrapling

**Repo:** https://github.com/D4Vinci/Scrapling  
**License:** BSD-3-Clause  
**Rol:** Adaptive scraping, Playwright/browser, stealth, proxy, concurrent crawling.

### Güçlü olduğu yer

- JS-heavy siteler
- selector'ı sık değişen siteler
- normal HTTP request'in yetmediği yerler
- crawl / pause-resume
- proxy rotation

Adaptive selector yaklaşımı unattended VPS scraper için değerli.

### Karar

**P1. WebFetcher adayı.**

---

## 2.5 Crawl4AI

**Repo:** https://github.com/unclecode/crawl4ai  
**License:** Apache-2.0 + ek attribution requirement  
**Rol:** LLM/RAG odaklı web crawling ve Markdown extraction.

### Scrapling vs Crawl4AI

**Scrapling:**
- scraping/stealth tarafı daha merkezde
- adaptive selectors
- browser automation

**Crawl4AI:**
- LLM-ready content
- crawling
- Markdown
- RAG-oriented extraction

### Karar

İkisini production'a aynı anda koyma.

10–30 gerçek source ile benchmark:

- success rate
- latency
- RAM
- article quality
- anti-bot success
- maintenance burden

Kazanan primary `WebAdapter`, diğeri optional fallback olabilir.

---

## 2.6 Newspaper4k

**Repo:** https://github.com/AndyTheFactory/newspaper4k  
**License:** MIT ağırlıklı; bazı bundled bileşenlerde Apache-2.0  
**Rol:** News article/title/metadata extraction.

### Karar

**Trafilatura fallback** olarak düşünülebilir. İki extractor ile başlayıp sistemi gereksiz kompleks yapma.

---

## 2.7 news-please

**Repo:** https://github.com/fhamborg/news-please  
**License:** Apache-2.0  
**Rol:** News crawling + extraction.

Trafilatura'dan daha heavyweight.

### Karar

Şimdilik dependency yapma. Büyük news archive/backfill ihtiyacı olursa tekrar bak.

---

## 2.8 SearXNG

**Repo:** https://github.com/searxng/searxng  
**License:** AGPL-3.0  
**Rol:** Self-hosted metasearch.

### Bizde kullanım

İleride assistant:

> "AMD'nin bugün çıkan driver sorunlarını araştır"

gibi live-web query yapacaksa third-party search API yanında self-hosted search backend olabilir.

### Caveat

Search engine upstream'leri rate-limit/block uygulayabilir.  
Bunu mission-critical tek search provider yapmamak daha doğru.

### Karar

**P2. Search/Research modülü çıktığında.**

---

# 3. Document / files / knowledge ingestion

## 3.1 Docling

**Repo:** https://github.com/docling-project/docling  
**License:** MIT  
**Rol:** PDF, DOCX, PPTX, XLSX, HTML, EPUB, audio transcript formats, email formats, images vb. parse etmek.

Özellikle PDF layout/table/formula understanding tarafı güçlü.

### Bizde kullanım

İleride mobile app'ten:

- PDF yükle
- screenshot yükle
- Word dosyası yükle
- mail attachment kaydet

gibi akışlar geldiğinde:

```text
upload
  ↓
Docling
  ↓
structured document
  ↓
chunks + metadata
  ↓
pgvector / Search / Ask
```

### Karar

**P0/P1. Personal knowledge base planı varsa direkt değer katar.**

---

## 3.2 MarkItDown

**Repo:** https://github.com/microsoft/markitdown  
**License:** MIT  
**Rol:** Çeşitli dosyaları Markdown'a çevirmek.

Docling'e göre daha lightweight.

### Kullanım stratejisi

```text
simple formats → MarkItDown
complex PDF/layout → Docling
```

İlla ikisini de şart değil.

### Karar

**P2 / lightweight fallback.**

---

# 4. Mobile app / sync / offline-first

Bu alan gelecekteki custom mobile app için en önemli mimari kararlardan biri.

## Temel problem

Sadece REST API + online requests ile mobile app yapmak kolaydır ama:

- offline iken task ekleyemezsin,
- UI network latency'ye bağlı olur,
- background sync zorlaşır,
- conflict handling sonradan bela olur.

Daha iyi model:

```text
Mobile UI
   ↓
Local DB
   ↓
background sync
   ↓
PostgreSQL
```

---

## 4.1 RxDB

**Repo:** https://github.com/pubkey/rxdb  
**License:** Apache-2.0  
**Rol:** Local-first reactive JS database + replication.

Web/JS/React Native tarafında güçlü.

Replication için mevcut backend'e birkaç sync endpoint ekleyerek çalışabilir; belirli bir cloud backend zorunlu değil.

### Bizde kullanım

React Native seçersek:

```text
React Native
   ↓
RxDB local database
   ↕
FastAPI sync endpoints
   ↕
PostgreSQL
```

### Artıları

- strict OSS
- reactive UI
- offline-first
- existing backend'i çöpe atmıyor
- backend-agnostic

### Eksileri

- JS ecosystem ağırlıklı
- sync protocol'ü yine bizim backend'e düzgün bağlamamız gerekiyor

### Karar

**React Native kullanacaksak en güçlü adaylardan biri.**

---

## 4.2 Electric

**Repo:** https://github.com/electric-sql/electric  
**License:** Apache-2.0  
**Rol:** PostgreSQL realtime sync / partial replication.

Electric'in mevcut mimarisi özellikle **read-path sync** tarafına odaklı.

```text
Postgres
  ↓
Electric Shapes
  ↓
mobile/web/local client
```

### Artıları

- bizim Postgres merkezli mimariye doğal uyuyor
- strict OSS
- partial replication
- realtime data delivery

### Eksileri

Writes için yine backend API / mutation path tasarımı gerekiyor.

### Karar

**P1 benchmark.**

Özellikle:

- briefing
- notifications state
- read models
- feed/timeline

sync'i için çok mantıklı olabilir.

---

## 4.3 PowerSync

**Client repos:**
- JS/React Native: https://github.com/powersync-ja/powersync-js
- Flutter/Dart: https://github.com/powersync-ja/powersync.dart

**Client SDK license:** Apache-2.0  
**Server:** https://github.com/powersync-ja/powersync-service  
**Server license:** FSL-1.1-ALv2 — **source-available, strict open source değil**.

### Teknik olarak neden çok iyi?

Client SQLite'a read/write yapılır ve backend ile background sync olur.

Flutter dahil mobile tarafında DX güçlü.

### Ama

Kullanıcının “açık kaynak olsun” şartı strict ise server tarafında caveat var.

### Karar

**Teknik benchmark listesinde tut; strict OSS kriteri yüzünden default seçim yapma.**

---

## 4.4 Supabase

**Repo:** https://github.com/supabase/supabase  
**Rol:** Postgres + Auth + Realtime + Storage + Functions.

### Bizde kullanım

Mobile app için Auth/Realtime/Storage hazır olabilir.

Ama mevcut backend zaten:

- PostgreSQL
- application API
- ingestion
- admin logic

barındırıyorsa komple Supabase migration gereksiz olabilir.

### Karar

**Platform migration yapma.**  
Sadece spesifik bir bileşeni gerçekten development süresi azaltacaksa değerlendir.

---

## 4.5 Appwrite

**Repo:** https://github.com/appwrite/appwrite  
**Rol:** Auth, DB, Storage, Functions, Messaging, Realtime.

Supabase'e alternatif all-in-one backend.

### Karar

Aynı sebeple mevcut backend'in yerine geçirmek şu an gereksiz.

**Reference / future greenfield mobile project** için anlamlı.

---

# 5. Task app / Calendar / interoperability

Burada iki gerçekçi strateji var.

---

## Strategy A — Task backend bizim PostgreSQL'de

```text
AI Assistant
      │
      ▼
TaskService (our FastAPI)
      │
 PostgreSQL canonical
      │
      ├── Web
      ├── Mobile
      └── AI tools
```

Avantaj:

- tek source of truth
- event/claim/memory ile ilişkiler kolay
- tamamen kontrol bizde

Bunu mobile tarafında RxDB/Electric gibi sync katmanıyla güçlendiririz.

---

## Strategy B — Vikunja task engine olarak

### Vikunja

**Repo:** https://github.com/go-vikunja/vikunja  
**License:** AGPL-3.0  
**Rol:** Mature self-hosted task backend.

Özellikler:

- tasks
- subtasks
- priorities
- status
- attachments
- project/list structure
- relations
- REST API
- CalDAV

### Büyük avantaj

Task backend'in %70–90'ını yeniden yazmayız.

Kendi mobil uygulamamız:

```text
Our Mobile UI
    ↓
Vikunja API
```

AI Assistant:

```text
Assistant
   ↓
Vikunja adapter
   ↓
same tasks
```

External apps:

```text
CalDAV
```

### Risk

- task data modelimiz Vikunja modeline bağımlı olur
- AGPL network-copyleft şartlarını ürünleştirirken dikkate almak gerekir
- 2026'da CalDAV authorization açığı vardı; **2.3.0'da patch edildi**, eski sürüm deploy edilmemeli

### Karar

**Ciddi benchmark et.**

Özellikle kendi task backend'ini sıfırdan yazmak yerine Vikunja'yı engine olarak kullanmak development süresini ciddi azaltabilir.

---

## 5.2 Radicale

**Repo:** https://github.com/Kozea/Radicale  
**License:** GPL-3.0  
**Rol:** Lightweight CalDAV/CardDAV server.

Takvim, todo ve contacts sync standardı sağlar.

### Ne zaman mantıklı?

Eğer bizim sistem:

- Apple Calendar
- Thunderbird
- DAVx5
- başka CalDAV task clients

ile konuşsun istiyorsak.

### Karar

Task verisinin canonical store'u olarak başlamazdım.

Daha iyi yaklaşım:

```text
our TaskService
   ↕
CalDAV adapter
```

Ancak CalDAV implementation'ını kendimiz yazmak istemiyorsak Radicale/Xandikos reference olabilir.

---

## 5.3 Nextcloud Tasks

**Repo:** https://github.com/nextcloud/tasks  
**License:** AGPL-3.0  
**Rol:** CalDAV tabanlı task app.

Direct dependency'den çok:

- data model
- CalDAV compatibility
- task UX

reference olarak değerli.

---

## 5.4 Tasks.org

**Repo:** https://github.com/tasks/tasks  
**Rol:** Android/Desktop open-source task client, CalDAV / EteSync / Google Tasks gibi sync kaynakları destekliyor.

Kendi mobile app'imizi yaparken özellikle:

- local task UX
- recurrence
- reminders
- tag sync
- CalDAV behavior

için iyi reference.

---

# 6. Mobile API client generation

## OpenAPI Generator

**Repo:** https://github.com/OpenAPITools/openapi-generator  
**License:** Apache-2.0

Bu proje bizim için beklenenden daha önemli.

FastAPI zaten OpenAPI schema üretir:

```text
FastAPI
  ↓
/openapi.json
  ↓
OpenAPI Generator
  ├ Dart SDK
  ├ Kotlin SDK
  ├ Swift SDK
  ├ TypeScript SDK
  └ ...
```

### Sonuç

Mobil uygulamada elle:

```text
GET /tasks
POST /tasks
GET /briefings
POST /feedback
...
```

client class'ları yazmayız.

Backend endpoint değiştiğinde SDK regenerate edilir.

### Karar

**P0 — şimdi bile CI'a konabilir.**

Bu ileride mobile app development'ı ciddi hızlandırır.

---

# 7. External apps / tools / actions

AI Assistant sadece bilgi okumayacak; ileride action da yapacak:

- task oluştur
- calendar event ekle
- email draft et
- GitHub issue aç
- notification gönder
- file kaydet
- uygulamalar arası işlem yap

Bunun için her API'yi sıfırdan entegre etmek mantıksız.

---

## 7.1 Model Context Protocol — MCP Servers

**Repo:** https://github.com/modelcontextprotocol/servers  
**Rol:** MCP reference servers + ecosystem entry point.

### Bizde kullanım

Internal tool abstraction'ı MCP-compatible tutabiliriz:

```text
Assistant Agent
      ↓
    MCP
      ├ Gmail
      ├ Calendar
      ├ GitHub
      ├ Files
      ├ Search
      └ custom Task MCP
```

### En büyük kazanım

AI layer ile integrations layer birbirine hard-code olmaz.

### Karar

**P1. Tool architecture'ın default interface'i olmaya aday.**

---

## 7.2 Activepieces

**Repo:** https://github.com/activepieces/activepieces  
**License:** Community/core MIT, enterprise folders commercial  
**Rol:** Workflow automation + yüzlerce integration/MCP.

### Bizde neden ilginç?

Hazır connector ecosystem'i var.

Ama bizim zaten scheduler/orchestration tarafında kendi backend + geçmişte n8n/Hermes planı varsa:

> n8n + Activepieces + Hermes + custom scheduler

şeklinde infra çorbası yapmamalıyız.

### Karar

**Install etmekten önce connector code / MCP ecosystem reference olarak incele.**

Bir orchestration product seç; üç tane aynı işi yapan sistem çalıştırma.

---

## 7.3 Composio

**Repo:** https://github.com/ComposioHQ/composio  
**Repo license:** MIT

1000+ toolkits, auth, tool search ve agent adapters sunuyor.

### Caveat

SDK açık kaynak olsa da normal kullanım akışı `COMPOSIO_API_KEY` ve hosted Composio service'e dayanıyor.

Dolayısıyla:

**open-source SDK ≠ fully self-hosted integration infrastructure.**

### Karar

Rapid prototyping için çok güçlü.  
Tam self-host/private-first hedefte core dependency yapmadan önce deployment/auth modelini doğrula.

---

## 7.4 Nango

**Repo:** https://github.com/NangoHQ/nango  
**Rol:** OAuth/auth/token refresh + hundreds of API integrations.

Teknik olarak assistant integrations için mükemmel fit.

### Ancak

Repo **Elastic License** kullanıyor; strict OSI open-source olarak görmüyorum.

### Karar

Bu araştırmanın strict OSS şartında **primary recommendation değil**.

Yine de OAuth/token management architecture'ı reference olarak çok değerli.

---

# 8. Notifications

## 8.1 ntfy

**Repo:** https://github.com/binwiederhier/ntfy  
**Rol:** HTTP PUT/POST ile mobile/desktop push notification.

### Bizim için mükemmel intermediate çözüm

Kendi mobile app hazır olmadan:

```text
Assistant
  ↓
POST /my-topic
  ↓
ntfy
  ↓
phone notification
```

Daily briefing, urgent mail, reminder, job failure gibi şeyleri 10 dakikalık integration ile telefona ulaştırabilir.

Android ve iOS client mevcut; self-host edilebilir.

### Karar

**P0/P1 — hemen değer üretir.**

---

## 8.2 Apprise

**Repo:** https://github.com/caronc/apprise  
**License:** BSD-2-Clause  
**Rol:** Tek library üzerinden çok sayıda notification provider.

```text
our notifier
    ↓
Apprise
 ├ Telegram
 ├ Discord
 ├ Slack
 ├ Gotify
 └ ...
```

### Karar

Birden fazla notification channel desteklenecekse çok iyi abstraction.

Sadece kendi telefonumuza push atılacaksa ntfy daha basit.

---

## 8.3 Gotify

**Repo:** https://github.com/gotify/server  
**License:** MIT  
**Rol:** Self-hosted REST + WebSocket notification server.

ntfy ile aynı problemin başka çözümü.

### Karar

İkisini birden kullanma.

Personal assistant için ntfy'nin HTTP simplicity'si nedeniyle önce ntfy.

---

## 8.4 Novu

**Repo:** https://github.com/novuhq/novu  
**License:** Core MIT, enterprise code commercial  
**Rol:** Push + Email + SMS + Chat + In-App Inbox + notification workflows/preferences.

### Ne zaman anlamlı?

Tek-user personal assistant aşamasında fazla büyük.

Ama ürün:

- mobile app
- in-app inbox
- push
- email
- notification preferences
- digest rules

olan multi-user bir platforma dönerse çok güçlü.

### Karar

**Later-stage.**

---

# 9. LLM gateway / model management

## LiteLLM

**Repo:** https://github.com/BerriAI/litellm  
**License:** Core MIT; enterprise folder ayrı lisanslı  
**Rol:** Çok sayıda LLM provider'ı tek OpenAI-compatible API arkasına koymak.

### Bizde kullanım

```text
Assistant
   ↓
LiteLLM
   ├ OpenAI
   ├ Gemini
   ├ Anthropic
   ├ OpenRouter
   ├ local vLLM/Ollama
   └ fallback
```

### Sağladığı şeyler

- provider abstraction
- fallback
- routing
- cost tracking
- rate limits
- central config

### Karar

Model sayısı ve provider switching arttığında **P1**.

Şu an tek bir API wrapper ile işler basitse hemen eklemek şart değil.

---

# 10. Memory / personal context

## 10.1 Mem0

**Repo:** https://github.com/mem0ai/mem0  
**License:** Apache-2.0  
**Rol:** Persistent agent memory.

2026 tarafında entity linking, temporal retrieval ve multi-signal retrieval yaklaşımını geliştirmiş durumda.

### Bizim için önemli nokta

Biz zaten event/claim, source-backed knowledge ve interest memory benzeri bir sistem kuruyorsak Mem0'ı direkt geçirip her şeyi değiştirmek doğru değil.

Benchmark:

```text
50–200 gerçek memory queries
        ↓
our current memory
vs
Mem0
        ↓
precision / recall / token / latency
```

### Karar

**P2 — benchmark.**

Mevcut memory'nin source provenance avantajını kaybetme.

---

## 10.2 Letta

**Repo:** https://github.com/letta-ai/letta  
**License:** Apache-2.0  
**Rol:** Stateful agents + long-term memory.

2026'da aktif core yeni `letta-code` tarafına taşınmış; eski server architecture archive/legacy durumda.

### Karar

Dependency olmaktan çok:

- agent memory model
- context management
- long-running identity

reference olarak incele.

---

# 11. Agent orchestration

## LangGraph

**Repo:** https://github.com/langchain-ai/langgraph  
**License:** MIT  
**Rol:** Stateful, long-running agents.

### Ne zaman gerek?

Current deterministic pipeline:

```text
ingest → extract → rank → brief
```

için LangGraph şart değil.

Ama ileride:

> "Bu maili oku, takvimime bak, uygun zaman bul, task oluştur, sonucu bana sor."

gibi multi-step action agent olduğunda:

```text
state
 ↓
tool
 ↓
decision
 ↓
human approval
 ↓
resume
```

flow yönetimi çok değerli olur.

### Karar

**Action-agent aşamasında P1/P2.**

Şimdiden core pipeline'a sokma.

---

# 12. Background jobs / queues / durable execution

## 12.1 PGMQ

**Repo:** https://github.com/pgmq/pgmq  
**Rol:** PostgreSQL içinde lightweight message queue.

Mevcut PostgreSQL'i kullanarak:

```text
ingestion jobs
transcript jobs
embedding jobs
briefing jobs
```

queue edilebilir.

### Avantaj

Redis/RabbitMQ gibi ekstra infra gerektirmez.

### Karar

Worker sayısı büyüyüp gerçek queue semantics gerektiğinde **çok mantıklı**.

---

## 12.2 pg_cron

**Repo:** https://github.com/citusdata/pg_cron  
**Rol:** PostgreSQL içinde cron scheduling.

### Karar

Basit DB-maintenance job'ları için güzel.

Application-level daily briefing orchestration'ı tamamen database içine gömmek istemem.

Örnek uygun kullanım:

- cleanup
- retention
- materialized view refresh
- maintenance

---

## 12.3 Hatchet

**Repo:** https://github.com/hatchet-dev/hatchet  
**Rol:** Background tasks, retry, durable workflows, DAG, rate limit, monitoring.

### Karar

Mevcut scheduler/worker yapısı yetersiz kaldığında Temporal'dan daha approachable bir seçenek olabilir.

Şimdi eklemek gereksiz.

---

## 12.4 Temporal

**Repo:** https://github.com/temporalio/temporal  
**License:** MIT  
**Rol:** Durable execution/workflows.

Çok güçlü ama bizim current scale için ağır.

### Karar

**Overkill now.**

İleride onlarca integration + multi-day agent workflow + retries + human approval ortaya çıkarsa yeniden bak.

---

# 13. Observability / evals

AI app'te klasik log yetmiyor. Şunları görmek gerekiyor:

- hangi prompt gitti
- hangi context retrieve edildi
- hangi tool çağrıldı
- model ne kadar token kullandı
- latency neydi
- cevap niye kötü çıktı

---

## 13.1 Langfuse

**Repo:** https://github.com/langfuse/langfuse  
**License:** Core MIT; `ee` folders enterprise  
**Rol:** LLM tracing, prompt management, evals, datasets, cost/latency.

### Karar

**P1.**

Özellikle production briefing neden kötü çıktı sorusunun cevabını bulmayı çok kolaylaştırır.

---

## 13.2 promptfoo

**Repo:** https://github.com/promptfoo/promptfoo  
**License:** MIT  
**Rol:** Prompt / RAG / Agent testing + red teaming.

### Bizde kullanım

CI regression set:

```text
input events
expected facts
expected citations
expected categories
forbidden hallucinations
```

Model/prompt değiştirilince otomatik test.

### Karar

**P1.**

LLM feature'larına unit-test disiplini getirir.

---

# 14. Voice — future

## Pipecat

**Repo:** https://github.com/pipecat-ai/pipecat  
**License:** BSD-2-Clause  
**Rol:** Realtime voice + multimodal agents.

STT → LLM → TTS streaming pipeline'ını yönetiyor.

### Ne zaman?

Mobil uygulamada:

> "Hey assistant, yarınki işlerimi söyle."

gibi live voice gelirse.

### Karar

Şu an değil. **Future P3.**

---

# 15. Full personal-assistant repos — dependency değil, architecture mine

Bu repoların en büyük değeri “kurup bizim sistemi atalım” değil.  
Bizim çözmeye çalıştığımız problemleri başka insanların nasıl çözdüğünü görmek.

---

## 15.1 Khoj

**Repo:** https://github.com/khoj-ai/khoj  
**License:** AGPL-3.0  
**Rol:** Self-hosted AI second brain.

Özellikleri bizim roadmap'e çok yakın:

- local/cloud LLM
- documents
- semantic search
- agents
- scheduled automations
- personal newsletters
- web
- desktop
- phone
- WhatsApp

### İncelenecek parçalar

- retrieval architecture
- user knowledge model
- scheduled automation UX
- cross-client access
- agent/tool boundaries

### Karar

**En önemli reference reposundan biri.**

---

## 15.2 ORDERLY

**Repo:** https://github.com/lerugray/orderly  
**Rol:** Self-hosted personal assistant: email + calendar + memory + web + briefing.

### Özellikle değerli fikir

Safety authorization'ı prompt'a bırakmıyor.

Örnek yaklaşım:

- mail read var
- draft var
- send permission yok
- calendar proposal var
- user approval ile write

Bu bizim action-agent için çok doğru security model:

> **“Agent'a yapma deme; teknik olarak yapamayacağı permission boundary koy.”**

### Karar

**Safety architecture reference.**

---

## 15.3 Leon

**Repo:** https://github.com/leon-ai/leon  
**Rol:** Open-source personal assistant, tools/context/memory/agentic execution.

2026'da 2.0 developer preview odaklı.

### Karar

Skill/module architecture reference olarak bak.  
Production dependency olarak acele etme.

---

## 15.4 Morning Deck

**Repo:** https://github.com/eschnou/morningdeck  
**Rol:** RSS + newsletters + websites + Reddit → interest scoring → daily briefing.

Bizim current briefing projesine çok yakın.

### İncelenecek

- source lifecycle
- interest scoring
- ranking
- daily briefing UX
- personalization
- search
- admin

### Karar

**Briefing architecture benchmark.**

---

## 15.5 Folo

**Repo:** https://github.com/RSSNext/Folo  
**License:** AGPL-3.0  
**Rol:** AI RSS reader / information hub.

### İncelenecek

- feed UX
- collections
- AI summary UI
- timeline
- subscription management

### Karar

Backend dependency değil; **mobile/web UI reference.**

---

## 15.6 AppFlowy

**Repo:** https://github.com/AppFlowy-IO/AppFlowy  
**License:** AGPL-3.0  
**Rol:** Open-source collaborative workspace / Notion alternative.

### Bizde kullanım

Task + notes + knowledge workspace UI tasarlarken:

- blocks
- workspace
- local data
- sync
- project organization

reference olabilir.

### Karar

Dependency değil. UX/data-model research.

---

## 15.7 Heatwire

**Repo:** https://github.com/NinjaCodeTurtle/heatwire  
**Rol:** News aggregation, embeddings, clustering, ranking.

Repo küçük/erken aşamada olduğu için production dependency olarak güvenilmez.

### Ama alınacak fikir

Aynı olayı anlatan 5 haberi 5 ayrı item değil, tek event yapmak:

```text
article A ─┐
article B ─┼── embedding similarity ──> EVENT
article C ─┘
```

Sonra source corroboration + recency score.

### Karar

**Algorithm/reference.**

---

# 16. Automation platforms — dikkatli kullan

## Windmill

**Repo:** https://github.com/windmill-labs/windmill  
**License:** AGPL-3.0 core + enterprise separation  
**Rol:** Scripts → APIs/jobs/workflows/UIs.

Python/TS/Go/Bash/SQL scripts, schedules, webhooks, workflows.

### Karar

Teknik olarak çok güçlü.

Ama:

```text
our scheduler
+ n8n
+ Hermes
+ Windmill
+ Activepieces
```

kurmak kötü architecture.

Bir orchestration layer seç.

---

## Huginn

**Repo:** https://github.com/huginn/huginn  
**Rol:** Self-hosted monitoring/automation agents.

### Karar

Bizim ingestion + scheduler ile büyük overlap.

**Kullanma; fikir/reference olabilir.**

---

# 17. Strict open-source / license caveats

“Açık kaynak” etiketi GitHub'da bazen yanıltıcı olabiliyor.

## Strict OSS tarafında rahat olduğumuz örnekler

- MIT
- Apache-2.0
- BSD
- GPL / AGPL

Bu araştırmada bu sınıfta:

- Trafilatura
- Scrapling
- RxDB
- Electric
- Docling
- MarkItDown
- OpenAPI Generator
- LangGraph
- Mem0
- ntfy
- Gotify
- Apprise
- promptfoo
- Temporal
- Pipecat
- Vikunja
- RSSHub
- Khoj
- Folo
- AppFlowy

gibi projeler var.

## Caveat olanlar

### PowerSync

Client SDK'ları Apache-2.0; **PowerSync Service FSL source-available**.

### Nango

Elastic License; strict OSI open-source değil.

### Composio

SDK MIT ama default kullanım hosted Composio API key/service gerektiriyor.

### Crawl4AI

Apache-2.0 metni yanında ekstra attribution requirement ekliyor.  
Public distribution durumunda license text'i ayrıca incelenmeli.

### Open-core projeler

Bazı projelerde core OSS, enterprise folder commercial:

- LiteLLM
- Langfuse
- Novu
- Activepieces

Personal self-host kullanımda genellikle sorun olmaz ama ürünleştirirken ilgili klasör/lisans ayrımı kontrol edilmeli.

---

# 18. Bizim proje için en mantıklı implementation roadmap

## Phase 1 — “Hazır değeri al”

### 1. OpenAPI Generator

FastAPI `/openapi.json` → generated SDK pipeline.

**Benefit:** mobile app başlayınca API client'ı sıfırdan yazmayız.

### 2. RSSHub

Yeni source coverage.

### 3. Trafilatura

Web article extraction.

### 4. youtube-transcript-api

YouTube içeriğini gerçekten anlayabilme.

### 5. ntfy

Own mobile app hazır olmadan phone notification.

### 6. Docling

Files / personal knowledge ingestion.

---

# Phase 2 — Data quality

### 7. Event clustering

Heatwire yaklaşımından:

- embeddings
- similarity
- time window
- source corroboration
- event centroid

alıp bizim event modeline uygula.

### 8. promptfoo regression suite

Briefing kalitesinin prompt/model değişiminde bozulmasını engelle.

### 9. Langfuse

Token/latency/trace visibility.

---

# Phase 3 — Task system

İki prototip yap:

## Prototype A

```text
Internal TaskService
Postgres
FastAPI
OpenAPI generated mobile SDK
```

## Prototype B

```text
Vikunja
REST API
CalDAV
our custom frontend
```

Kıyas:

- development time
- task model flexibility
- recurring tasks
- reminders
- relations/subtasks
- mobile sync
- AI tool integration
- long-term lock-in

Benim başlangıç bias'ım:

> Assistant'ın task data'sıyla memory/events arasında çok özel ilişkiler kuracaksak **internal TaskService** daha temiz.  
> Hızla mature task system istiyorsak **Vikunja backend** ciddi zaman kazandırır.

---

# Phase 4 — Mobile sync

Framework seçildikten sonra karar.

## React Native / JS ise

**RxDB first benchmark.**

## Flutter ise

- Electric + local SQLite/outbox architecture
- PowerSync benchmark (server license caveat kabul edilirse)

## Online-first MVP ise

İlk sürüm:

```text
generated SDK + REST
```

ile çıkar.

Offline-first complexity'yi MVP'ye zorla sokma; ama domain modelini ileride sync eklenebilecek şekilde tasarla.

---

# Phase 5 — Assistant actions

Tool boundary'yi:

```text
ToolRegistry / MCP
```

şeklinde tasarla.

İlk tools:

```text
task.read
task.create
calendar.read
calendar.propose
gmail.search
gmail.draft
briefing.search
web.search
```

Dangerous write'larda ORDERLY yaklaşımı:

```text
AI proposes
    ↓
human approves
    ↓
system executes
```

Permission scope prompt'tan bağımsız enforcement olmalı.

---

# Phase 6 — Advanced agent

Sadece gerektiğinde:

- LangGraph
- Mem0
- Hatchet/Temporal

ekle.

Bugün eklenirse abstraction tax yaratır.

---

# 19. Özellikle EKLEMEM dediğim şeyler

Şu aşamada:

- Temporal
- full Appwrite migration
- full Supabase migration
- Huginn
- Windmill + n8n aynı anda
- Activepieces + n8n aynı anda
- Mem0 ile mevcut memory'yi direkt replace etmek
- LangGraph ile deterministic briefing pipeline'ı yeniden yazmak
- Scrapling + Crawl4AI'ı aynı anda primary dependency yapmak
- Gotify + ntfy + Novu'nun üçünü birden çalıştırmak

**Rule:**

> Bir repo yeni capability getiriyorsa ekle.  
> Sadece mevcut capability'nin ikinci/üçüncü kopyasıysa ekleme.

---

# 20. Shortlist — Codex'e analiz ettirilecek repos

Codex'in sırayla incelemesi için:

```text
1. OpenAPITools/openapi-generator
2. DIYgod/RSSHub
3. adbar/trafilatura
4. jdepoix/youtube-transcript-api
5. docling-project/docling
6. D4Vinci/Scrapling
7. unclecode/crawl4ai
8. pubkey/rxdb
9. electric-sql/electric
10. go-vikunja/vikunja
11. modelcontextprotocol/servers
12. binwiederhier/ntfy
13. BerriAI/litellm
14. langfuse/langfuse
15. promptfoo/promptfoo
16. mem0ai/mem0
17. langchain-ai/langgraph
18. pgmq/pgmq
19. khoj-ai/khoj
20. lerugray/orderly
21. eschnou/morningdeck
22. RSSNext/Folo
23. AppFlowy-IO/AppFlowy
24. NinjaCodeTurtle/heatwire
```

---

# 21. Codex için repo-evaluation checklist

Her repo için otomatik karar verirken:

```text
[ ] Ne problemini çözüyor?
[ ] Biz bu problemi zaten çözdük mü?
[ ] Entegrasyon LOC tahmini?
[ ] Kaç Docker/service ekliyor?
[ ] Python/FastAPI/Postgres ile fit?
[ ] Self-host mümkün mü?
[ ] Strict OSS mi?
[ ] Network/cloud dependency var mı?
[ ] Son activity/release güncel mi?
[ ] Security history?
[ ] Data source of truth değişiyor mu?
[ ] Vendor lock-in?
[ ] Failure isolation var mı?
[ ] Kaldırması kolay mı?
[ ] Mevcut testleri kırmadan adapter olarak eklenebilir mi?
```

Bir repo ancak:

```text
benefit > operational complexity + lock-in + maintenance
```

ise integrate edilmeli.

---

# 22. Net final architecture recommendation

Bugün sıfırdan tekrar karar verecek olsam:

```text
FastAPI
PostgreSQL + pgvector
│
├── Sources
│   ├── RSS native
│   ├── RSSHub
│   ├── Gmail
│   ├── YouTube + youtube-transcript-api
│   └── Web
│       ├── Scrapling OR Crawl4AI
│       └── Trafilatura
│
├── Documents
│   └── Docling
│
├── Knowledge
│   ├── events
│   ├── claims
│   ├── interests
│   ├── embeddings
│   └── hybrid retrieval
│
├── Tasks
│   └── internal TaskService OR Vikunja adapter
│
├── API
│   └── OpenAPI Generator → mobile SDK
│
├── Sync
│   └── RxDB/Electric benchmark
│
├── Notifications
│   ├── ntfy now
│   └── Novu later
│
├── Models
│   └── LiteLLM when provider count grows
│
├── Tools
│   └── MCP-compatible ToolRegistry
│
├── Quality
│   ├── Langfuse
│   └── promptfoo
│
└── Advanced Agent (later)
    ├── LangGraph
    └── memory benchmark with Mem0
```

Bu yaklaşımın ana avantajı:

**Hazır açık kaynak projelerden leverage alıyoruz ama kendi AI Personal Assistant'ımızı 15 farklı framework'ün yapıştırıldığı Frankenstein stack'e çevirmiyoruz.**

---

# 23. Kaynak repos

## Ingestion / web

- RSSHub — https://github.com/DIYgod/RSSHub
- Trafilatura — https://github.com/adbar/trafilatura
- youtube-transcript-api — https://github.com/jdepoix/youtube-transcript-api
- Scrapling — https://github.com/D4Vinci/Scrapling
- Crawl4AI — https://github.com/unclecode/crawl4ai
- Newspaper4k — https://github.com/AndyTheFactory/newspaper4k
- news-please — https://github.com/fhamborg/news-please
- SearXNG — https://github.com/searxng/searxng

## Files / RAG

- Docling — https://github.com/docling-project/docling
- MarkItDown — https://github.com/microsoft/markitdown

## Sync / mobile

- RxDB — https://github.com/pubkey/rxdb
- Electric — https://github.com/electric-sql/electric
- PowerSync JS — https://github.com/powersync-ja/powersync-js
- PowerSync Dart — https://github.com/powersync-ja/powersync.dart
- PowerSync Service — https://github.com/powersync-ja/powersync-service
- Supabase — https://github.com/supabase/supabase
- Appwrite — https://github.com/appwrite/appwrite
- OpenAPI Generator — https://github.com/OpenAPITools/openapi-generator

## Tasks / calendar

- Vikunja — https://github.com/go-vikunja/vikunja
- Radicale — https://github.com/Kozea/Radicale
- Xandikos — https://github.com/jelmer/xandikos
- Nextcloud Tasks — https://github.com/nextcloud/tasks
- Tasks.org — https://github.com/tasks/tasks

## Tools / integrations / automation

- MCP Servers — https://github.com/modelcontextprotocol/servers
- Activepieces — https://github.com/activepieces/activepieces
- Composio — https://github.com/ComposioHQ/composio
- Nango — https://github.com/NangoHQ/nango
- Windmill — https://github.com/windmill-labs/windmill
- Huginn — https://github.com/huginn/huginn

## Notifications

- ntfy — https://github.com/binwiederhier/ntfy
- Apprise — https://github.com/caronc/apprise
- Gotify — https://github.com/gotify/server
- Novu — https://github.com/novuhq/novu

## AI / memory / orchestration

- LiteLLM — https://github.com/BerriAI/litellm
- Mem0 — https://github.com/mem0ai/mem0
- Letta — https://github.com/letta-ai/letta
- LangGraph — https://github.com/langchain-ai/langgraph
- PGMQ — https://github.com/pgmq/pgmq
- pg_cron — https://github.com/citusdata/pg_cron
- Hatchet — https://github.com/hatchet-dev/hatchet
- Temporal — https://github.com/temporalio/temporal

## Observability / testing

- Langfuse — https://github.com/langfuse/langfuse
- promptfoo — https://github.com/promptfoo/promptfoo

## Voice

- Pipecat — https://github.com/pipecat-ai/pipecat

## Full assistant / UX references

- Khoj — https://github.com/khoj-ai/khoj
- ORDERLY — https://github.com/lerugray/orderly
- Leon — https://github.com/leon-ai/leon
- Morning Deck — https://github.com/eschnou/morningdeck
- Folo — https://github.com/RSSNext/Folo
- AppFlowy — https://github.com/AppFlowy-IO/AppFlowy
- Heatwire — https://github.com/NinjaCodeTurtle/heatwire
