# CLAUDE.md — CivicSpace Bot: Setup & Deployment Workflow

## Overview

CivicSpace Bot เป็น Facebook Messenger Bot ที่ใช้ Python + Azure Bot Framework SDK + Google Gemini API
deploy บน Azure App Service ผ่าน GitHub Actions CI/CD

---

## Architecture

```
ผู้ใช้ (Facebook Messenger)
        │
        ▼
Facebook Page  ──(webhook: messages, messaging_postbacks)──►  Azure Bot Service
                                                                     │
                                                                     ▼
                              POST /api/messages  (aiohttp + CloudAdapter บน Azure App Service)
                                                                     │
                                              ┌──────────────────────┴───────────────────────┐
                                              │  CivicSpaceBot (bot.py)                        │
                                              │   - เก็บ conversation history (10 turn ล่าสุด) │
                                              │   - ส่งเข้า Gemini พร้อม SYSTEM_PROMPT          │
                                              └──────────────────────┬───────────────────────┘
                                                                     ▼
                                          Google Gemini API (gemini-2.5-flash)
                                          system_instruction = persona + knowledge/*.md
                                                                     │
                                                                     ▼
                                              ตอบกลับ → Azure Bot → Messenger → ผู้ใช้
```

- **บุคลิก/กฎเหล็ก/แนวทางตอบ** อยู่ใน `config.py` (`SYSTEM_PROMPT`)
- **ฐานความรู้ (ข้อเท็จจริง)** อยู่ใน `knowledge/*.md` โหลดรวมเข้า prompt อัตโนมัติ — เพิ่มประเด็นใหม่ได้โดยไม่ต้องแตะโค้ด

---

## Tech Stack

| Component | Detail |
|-----------|--------|
| Runtime | Python 3.11 |
| Web Framework | aiohttp |
| Bot Framework | botbuilder-core 4.16.2, botbuilder-integration-aiohttp 4.16.2 |
| AI | google-genai 1.21.1 (Gemini 2.5 Flash) |
| Hosting | Azure App Service (Linux, Southeast Asia, B1) |
| CI/CD | GitHub Actions → azure/webapps-deploy@v3 |
| Port | 3978 |

---

## Key Files

| File / Dir | หน้าที่ |
|------------|---------|
| `app.py` | Entry point — aiohttp server, `CloudAdapter`, route `POST /api/messages` + health `GET /`, factory `init_func` |
| `bot.py` | `CivicSpaceBot` — จัดการข้อความ, คำทักทาย, เก็บ conversation history (10 turn ล่าสุดต่อห้องแชต) |
| `gemini_client.py` | Wrapper รอบ google-genai (async) — ส่ง history + system prompt + `temperature=0.3` |
| `config.py` | โหลด env vars, `SYSTEM_PROMPT` (persona + กฎเหล็ก), `load_knowledge()` รวมไฟล์ใน `knowledge/` |
| `knowledge/*.md` | ฐานความรู้แบบแยกไฟล์ต่อประเด็น โหลดอัตโนมัติ (ไฟล์ขึ้นต้น `_` ไม่ถูกโหลด) |
| `knowledge/_HOWTO.md` | คู่มือทีมสำหรับเพิ่ม/แก้ฐานความรู้ |
| `BOT.md` | สเปกบอท (Single Source of Truth) — persona, กฎเหล็ก, few-shot, system prompt |
| `requirements.txt` | Python dependencies |
| `Procfile` | คำสั่งรันสำรอง (`python -m aiohttp.web ... app:init_func`) |
| `.env.example` | เทมเพลต env vars (ค่าจริงอยู่ใน `.env` ซึ่ง gitignore ไว้) |
| `.github/workflows/azure-deploy.yml` | GitHub Actions: push main → deploy ขึ้น Azure |

---

## Azure App Service Configuration

**Web App Name:** `civic-bot-app`  
**Resource Group:** `civicspace_group`  
**URL:** `https://civic-bot-app.azurewebsites.net`  
**Messaging Endpoint:** `https://civic-bot-app.azurewebsites.net/api/messages`

### Startup Command (CRITICAL)
```bash
python -m aiohttp.web -H 0.0.0.0 -P 3978 app:init_func
```

ตั้งผ่าน CLI:
```bash
az webapp config set \
  --resource-group civicspace_group \
  --name civic-bot-app \
  --startup-file "python -m aiohttp.web -H 0.0.0.0 -P 3978 app:init_func"
```

### Environment Variables (App Settings)
```bash
az webapp config appsettings set \
  --resource-group civicspace_group \
  --name civic-bot-app \
  --settings \
    MICROSOFT_APP_ID="1bd2c7e9-fbeb-4f26-b554-192b70c3580e" \
    MICROSOFT_APP_TYPE="SingleTenant" \
    MICROSOFT_APP_TENANTID="115bcbba-a469-4210-ac6b-e1a5e062f6b3" \
    MICROSOFT_APP_PASSWORD="<secret>" \
    GEMINI_API_KEY="<secret>" \
    GEMINI_MODEL="gemini-2.5-flash" \
    PORT=3978 \
    WEBSITES_PORT=3978
```

> ⚠️ **WEBSITES_PORT=3978 สำคัญมาก** — ถ้าไม่ตั้ง Azure จะ health check port 8000 แต่ app ฟังที่ 3978 ทำให้ ContainerTimeout

---

## GitHub Actions Workflow

File: `.github/workflows/azure-deploy.yml`

- Trigger: push to `main` หรือ `workflow_dispatch`
- Secret ที่ต้องตั้ง: `AZURE_WEBAPP_PUBLISH_PROFILE`

### วิธีได้ Publish Profile
```bash
# ต้องเปิด Basic Auth ก่อน
az resource update \
  --resource-group civicspace_group \
  --name scm \
  --namespace Microsoft.Web \
  --resource-type basicPublishingCredentialsPolicies \
  --parent sites/civic-bot-app \
  --set properties.allow=true

# ดึง publish profile
az webapp deployment list-publishing-profiles \
  --resource-group civicspace_group \
  --name civic-bot-app \
  --xml

# ตั้ง GitHub secret
gh secret set AZURE_WEBAPP_PUBLISH_PROFILE \
  --repo cabindev/civicbot \
  --body "$(az webapp deployment list-publishing-profiles \
    --resource-group civicspace_group \
    --name civic-bot-app --xml)"
```

---

## Azure Bot Service / Facebook Channel

| Setting | Value |
|---------|-------|
| Facebook Page ID | 728353493701593 |
| Facebook App ID | 1007274552043694 |
| Azure Bot resource | `civic-bot` |
| Verify Token | Azure สร้างให้เอง ดูได้ที่ Bot `civic-bot` → Channels → Facebook |
| Callback URL (ใส่ที่ Meta) | `https://facebook.botframework.com/api/v1/bots/civic-bot` |
| Messaging Endpoint (Azure Bot → App Service) | `https://civic-bot-app.azurewebsites.net/api/messages` |
| Subscribed Fields | messages, messaging_postbacks |

> ⚠️ **สอง URL นี้คนละตัวกัน อย่าสลับ** — Callback URL คือทางที่ Facebook ยิงเข้า Bot Framework
> ส่วน Messaging Endpoint คือทางที่ Bot Framework ยิงต่อเข้า App Service ของเรา
> ใส่ Messaging Endpoint ลงช่อง Callback URL ที่ Meta = webhook ใช้ไม่ได้

---

## One-Time Setup Checklist (ถ้าต้องทำใหม่)

- [ ] **สร้าง Azure resources** — Resource Group `civicspace_group`, App Service (Linux, Python 3.11, B1), Azure Bot resource
- [ ] **ตั้ง Startup Command** (ดูหัวข้อ Startup Command ด้านบน)
- [ ] **ตั้ง App Settings / env vars** ครบทุกตัว รวม `WEBSITES_PORT=3978` (ดูหัวข้อ Environment Variables)
- [ ] **เปิด Basic Auth** บน App Service (สำหรับ publish profile)
- [ ] **ดึง Publish Profile** แล้วตั้งเป็น GitHub secret `AZURE_WEBAPP_PUBLISH_PROFILE`
- [ ] **Push to `main`** → ปล่อยให้ GitHub Actions deploy
- [ ] **Health check** — `curl .../` ต้องได้ `{"status":"ok"}`
- [ ] **ตั้ง Messaging Endpoint** ใน Azure Bot = `.../api/messages`
- [ ] **เพิ่ม Facebook Channel** ใน Azure Bot — ใส่ Page Access Token, App Secret, Verify Token
- [ ] **ตั้ง Webhook** ใน Facebook App — URL = endpoint, subscribe fields: `messages`, `messaging_postbacks`
- [ ] **ทดสอบ** — ส่งข้อความจาก Messenger ของเพจ ดูว่าบอทตอบ

---

## Common Errors & Fixes

| Error | สาเหตุ | วิธีแก้ |
|-------|--------|---------|
| `ContainerTimeout` / `Site startup probe failed after 230s` | WEBSITES_PORT ไม่ตรงกับ PORT ของ app | ตั้ง `WEBSITES_PORT=3978` และ startup command ใช้ port 3978 |
| `Application Error` (curl) | Startup Command ว่าง หรือ app crash | ตรวจ log: `az webapp log tail --provider docker` |
| GitHub Actions Deploy failed | Basic Auth ปิดอยู่ | `az resource update ... --set properties.allow=true` |
| `token is not valid for page` | ใช้ Page ID หรือ Token ผิด | เรียก Graph API `/me/accounts` หา Page Access Token ที่ถูกต้อง |
| Webhook verify failed | Verify Token ไม่ตรง | Copy token จาก Azure Bot Channel โดยตรง |

---

## Health Check

```bash
# ตรวจว่า app up
curl -s https://civic-bot-app.azurewebsites.net/
# ผล: {"status": "ok", "service": "civicspace-bot"}

# ดู logs realtime
az webapp log tail --resource-group civicspace_group --name civic-bot-app --provider docker

# ดู startup command ปัจจุบัน
az webapp config show --resource-group civicspace_group --name civic-bot-app --query "appCommandLine" -o tsv

# ดู env vars ปัจจุบัน
az webapp config appsettings list --resource-group civicspace_group --name civic-bot-app -o table
```

---

## Redeploy (everyday workflow)

```bash
# แค่ push to main branch
git add .
git commit -m "your message"
git push origin main
# GitHub Actions จะ deploy ให้อัตโนมัติ
```

## Rebuild (2026-08-18) — กู้คืนหลัง Azure resources ถูกลบ

App Service `civic-bot-app` เดิม และ Azure Bot resource ถูกลบไป (App Service Plan เดิม
ถูกนำไปรัน Django app `civicspace` แทน) สร้างใหม่แล้วดังนี้

**สิ่งที่รอดมา ไม่ต้องสร้างใหม่:** App Registration `civic-bot` (`1bd2c7e9-…`, SingleTenant)
พร้อม client secret (หมดอายุ 2026-12-21 และ 2028-06-24) → `MICROSOFT_APP_ID` / `MICROSOFT_APP_PASSWORD` เดิมยังใช้ได้

**สิ่งที่สร้างใหม่:**

| รายการ | ค่า |
|--------|-----|
| App Service | `civic-bot-app` บน ASP เดิม `ASP-civicspacegroup-9d1b` (B1 Linux, **แชร์กับ Django app `civicspace`**) |
| Hostname | `civic-bot-app.azurewebsites.net` (สั้นลง ไม่มี random suffix) — **เปลี่ยนจากเดิม** |
| Azure Bot | `civic-bot` (SKU F0, global) ผูก app registration เดิม |
| Publish profile | ออกใหม่ → GitHub secret `AZURE_WEBAPP_PUBLISH_PROFILE` |

> ⚠️ **ASP แชร์กับ Django app** — B1 มี 1 core / 1.75 GB memory อยู่ที่ ~70% หลังเพิ่มบอท
> (บอทกินเพิ่มแค่ ~1%) ถ้าอนาคตเว็บโหลดหนัก ให้แยก plan ก่อนที่จะเริ่ม OOM

### Hardening เพื่อความต่อเนื่อง (2026-08-18)

| ตั้งค่า | ค่า | เหตุผล |
|---------|-----|--------|
| `alwaysOn` | `true` | **สำคัญที่สุด** — ถ้าปิด Azure จะ unload app หลัง idle 20 นาที ทำให้ข้อความแรกเจอ cold start ~24 วิ ซึ่งนานกว่า timeout ของ Bot Framework → ข้อความแรกหายเงียบทุกครั้ง (วัดจริง: cold 23.8s → warm 0.22s) |
| `healthCheckPath` | `/` | Azure ping เอง ถ้า instance ไม่ตอบจะรีสตาร์ทให้อัตโนมัติ |
| `httpsOnly` | `true` | endpoint เปิดสาธารณะ บังคับ TLS |
| `http20Enabled` | `true` | ลด overhead ต่อ request |
| Application logging | filesystem, level `Information` | ไล่ปัญหาได้ด้วย `az webapp log tail` |
| Resource lock | `CanNotDelete` บน `civic-bot-app` และ `civic-bot` | กันโดนลบซ้ำแบบที่เกิดเมื่อ ส.ค. 2026 |

> ⚠️ **Memory หลังเปิด Always On** — ขึ้นจาก ~69% เป็น ~77% (max 80%) ของ B1 1.75 GB
> เพราะบอทค้างใน RAM ตลอดแทนที่จะถูก unload เหลือ headroom ~400 MB
> ถ้าเห็นแตะ 90% ขึ้นไปบ่อย ให้แยก App Service Plan ออกจาก Django app

**คำสั่งลบ lock ตอนที่ต้องลบ resource จริง ๆ:**
```bash
az lock delete --name civic-bot-app-nodelete -g civicspace_group \
  --resource-name civic-bot-app --resource-type Microsoft.Web/sites
```

### 🔑 Client secret (rotate แล้ว 2026-08-18)

App registration `civic-bot` มี secret 3 ตัว **ตัวที่ใช้งานจริงคือ `civic-bot-renewal-2026-08`**

| Description | หมดอายุ | สถานะ |
|---|---|---|
| `civic-bot-renewal-2026-08` | **2028-08-17** | ✅ ใช้งานอยู่ (ทั้ง Azure App Settings และ `.env`) |
| `civic-bot-gemini` (hint `Nk1`) | 2026-12-21 | สำรอง — ลบได้หลังยืนยันว่าบอทเสถียร |
| (ไม่มีชื่อ, hint `1w5`) | 2028-06-24 | ไม่ได้ใช้ ดึงค่าคืนไม่ได้ |

ยืนยันแล้วว่าขอ token จาก Entra ID (`scope=https://api.botframework.com/.default`) ผ่านจริง

**วิธี rotate รอบหน้า (ก่อน ส.ค. 2028):**

```bash
# ต้องมี --append เสมอ ไม่งั้น secret เดิมถูกลบทั้งหมด บอทตายทันที
az ad app credential reset --id 1bd2c7e9-fbeb-4f26-b554-192b70c3580e \
  --append --years 2 --display-name "civic-bot-renewal-YYYY-MM" --query password -o tsv
```

จากนั้นเอาค่าไปใส่ทั้ง Azure App Settings และ `.env`

> ⚠️ **อย่าใช้ `sed` กับค่า secret** — Entra secret มีอักขระอย่าง `|` `~` `/` `+` ปนอยู่
> ซึ่งชนกับ delimiter ของ sed ให้ใช้ python อ่านผ่าน env var แทน (delimiter-safe)
>
> ```bash
> NEW="<ค่าใหม่>" python3 -c 'import os,io
> new=os.environ["NEW"]; p=".env"
> ls=io.open(p,encoding="utf-8").read().splitlines(True)
> out=[("MICROSOFT_APP_PASSWORD=\"%s\"\n"%new) if l.startswith("MICROSOFT_APP_PASSWORD=") else l for l in ls]
> io.open(p,"w",encoding="utf-8").write("".join(out))'
> ```
>
> และเวลาทดสอบ token ให้ใช้ `curl --data-urlencode "client_secret=$NEW"` ไม่ใช่ `-d` เฉย ๆ
> เพราะอักขระพิเศษจะถูกเข้ารหัสผิดแล้วได้ผลลวง

---

### ✅ Facebook Channel (เชื่อมสำเร็จ 2026-08-18)

บอทตอบใน Messenger ของเพจ CivicSpace ได้จริงแล้ว ยืนยันด้วยการทดสอบส่งข้อความ

| ค่า | สถานะ |
|---|---|
| Azure `configuredChannels` | `["webchat", "directline", "facebook"]` |
| Facebook App ID | `1007274552043694` |
| Page ID | `728353493701593` |
| Callback URL (ฝั่ง Meta) | `https://facebook.botframework.com/api/v1/bots/civic-bot` |
| Subscribed fields | `messages`, `messaging_postbacks` (+ `message_deliveries`, `messaging_optins`) |

**สิ่งที่เอกสารเดิมเข้าใจผิด — Azure ตั้ง webhook ฝั่ง Meta ให้อัตโนมัติ**

พอกรอกฟอร์ม Facebook channel ใน Azure สำเร็จ Azure จะไปตั้ง Callback URL และ Verify Token
ในหน้า Meta Webhooks ให้เอง **ไม่ต้อง copy ไปวางเอง** ตามที่เคยเขียนไว้

ทิศทางการไหลของค่า (จุดที่สับสนบ่อยที่สุด):

```
Meta  ──► Azure   App ID, App Secret, Page ID, Page Access Token   (กรอกเอง)
Azure ──► Meta    Callback URL, Verify Token                       (อัตโนมัติ)
```

> **Callback URL ที่ Meta ต้องใช้คือ `https://facebook.botframework.com/api/v1/bots/civic-bot`**
> ไม่ใช่ `https://civic-bot-app.azurewebsites.net/api/messages` — อันหลังคือทางที่ Azure Bot
> คุยกับ App Service ของเรา ไม่ใช่ทางที่ Facebook ยิงเข้ามา

### ⚠️ App Review ยังไม่ผ่าน — บอทยังไม่เปิดสาธารณะ

Meta app อยู่ใน **Development mode** (Messenger checklist ข้อ 3 ยังไม่ติ๊ก) ผลคือ

- ✅ คนที่มี role ในแอป (Admin / Developer / Tester) ทักแล้วบอทตอบปกติ
- ❌ **คนทั่วไปทักแล้วบอทจะเงียบ** — ไม่ใช่บั๊ก แต่ Meta บล็อกไว้

ถ้าจะเปิดให้สาธารณะใช้ ต้องยื่น App Review ขอ permission `pages_messaging`
เป็นกระบวนการฝั่ง Meta ใช้เวลาหลายวัน

### วิธีไล่ปัญหาเมื่อบอทเงียบ

**อ่าน log เป็นอย่างแรก** มันแยกได้ทันทีว่าพังฝั่งไหน

```bash
# ดาวน์โหลด log (ดูย้อนหลังได้ ดีกว่า log tail เวลาไล่เหตุที่เกิดไปแล้ว)
az webapp log download -g civicspace_group -n civic-bot-app --log-file logs.zip
unzip -o -q logs.zip -d logs
grep -h "BF-Facebook" logs/LogFiles/*docker.log | tail -20
```

แถวที่ขึ้นต้นด้วย `BF-Facebook` คือข้อความที่ Facebook ส่งเข้ามา อ่าน HTTP code ท้ายบรรทัด

| ผลที่เห็น | แปลว่า | แก้ที่ไหน |
|---|---|---|
| `HTTP 201` | ปกติ บอทตอบสำเร็จ | — |
| `HTTP 500` + `(ServiceError) Facebook API error` | **ขาเข้าดี ขาออกพัง** — credential ที่ Azure ใช้ส่งข้อความกลับใช้ไม่ได้ | Azure Bot → Channels → Facebook |
| `HTTP 401` | JWT ไม่ผ่าน | `MICROSOFT_APP_PASSWORD` หมดอายุ/ไม่ตรง |
| ไม่มีแถว `BF-Facebook` เลย | Facebook ไม่ได้ส่งมา | webhook ฝั่ง Meta / App Review |

### เคสจริง 2026-08-18 — บอทเงียบสนิทเพราะ Facebook credential

บอททำงานปกติตอน 12:32–13:49 แล้วเงียบสนิทตั้งแต่ 14:25 ผู้ใช้ไม่เห็นแม้แต่ข้อความ error

log ชี้ชัด: `POST /api/messages` จาก `BF-Facebook` ได้ **HTTP 500** พร้อม
`ErrorResponseException: (ServiceError) Facebook API error` เกิดซ้ำ 15 ครั้ง

**ทำไมผู้ใช้ไม่เห็นอะไรเลย** — `on_error` ใน `app.py` พยายามส่งข้อความ "ขออภัย ระบบขัดข้อง"
กลับไป แต่การส่งนั้นก็ใช้ช่องทางเดียวกันที่พังอยู่ จึง fail ซ้ำ ผู้ใช้เลยเจอความเงียบ
ไม่ใช่ข้อความ error

**สาเหตุ** — Page Access Token / App Secret ที่ Facebook channel เก็บไว้ใช้ไม่ได้แล้ว
เกิดได้ 2 ทาง

1. **Page Access Token หมดอายุ** — token จาก Graph Explorer เป็น short-lived (~1 ชม.)
   ถ้าไม่ Extend ก่อน บอทจะทำงานได้ไม่กี่ชั่วโมงแล้วเงียบ
2. **reset App Secret แล้วไม่ได้อัปเดตใน Azure** — Azure ยังถือตัวเก่า เรียก Facebook API ไม่ผ่าน

**วิธีแก้** — Azure Bot → Channels → Facebook แล้วใส่ **ทั้ง App Secret และ Page Access Token
ตัวล่าสุดใหม่ทั้งคู่** (อย่าใส่ทีละตัว จะไล่ไม่จบว่าตัวไหนพัง) แล้ว Apply

> ⚠️ **Extend token ทุกครั้งก่อนเอามาใช้** ที่ developers.facebook.com/tools/accesstoken/
> กด **Extend Access Token** ให้เป็น long-lived ไม่งั้นจะกลับมาเงียบอีกในไม่กี่ชั่วโมง

**ยืนยันว่าหายแล้ว** — เทียบ etag ของ channel ว่าเปลี่ยนไหม แล้วให้คนทักมาหนึ่งข้อความ
จากนั้นโหลด log ดูว่ากลับเป็น `HTTP 201`

```bash
az bot facebook show -g civicspace_group -n civic-bot --query "etag" -o tsv
```



---

*Last updated: 2026-08-18 | Setup: cabindev + Claude | Rebuilt after Azure resources were deleted (see “Rebuild” section above)*
