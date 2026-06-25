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
**URL:** `https://civic-bot-app-ftfkffgja6ahgne8.southeastasia-01.azurewebsites.net`  
**Messaging Endpoint:** `https://civic-bot-app-ftfkffgja6ahgne8.southeastasia-01.azurewebsites.net/api/messages`

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
| Verify Token | เก็บใน Azure Bot Facebook Channel settings |
| Webhook URL | `https://civic-bot-app-ftfkffgja6ahgne8.southeastasia-01.azurewebsites.net/api/messages` |
| Subscribed Fields | messages, messaging_postbacks |

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
curl -s https://civic-bot-app-ftfkffgja6ahgne8.southeastasia-01.azurewebsites.net/
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

---

*Last updated: 2026-06-25 | Setup completed by: cabindev + Claude*
