#!/usr/bin/env bash
# ตรวจสุขภาพ credential ของ Facebook channel ที่ Azure ถืออยู่
#
#   ./tools/check-fb-token.sh
#
# ดึงค่าจาก Azure โดยตรง (ไม่ต้องเปิด Graph Explorer ไม่ต้อง copy อะไร)
# แล้วยิง debug_token ไปถาม Facebook ว่า token ยังใช้ได้และเหลืออายุเท่าไร
#
# ไม่พิมพ์ค่า secret หรือ token ออกมาเลย — แสดงเฉพาะผลตรวจ
# exit 0 = ปกติ / exit 1 = มีปัญหา (ใช้ต่อใน cron หรือ monitor ได้)
#
# ต้อง az login ไว้ก่อน และมีสิทธิ์อ่าน bot resource

set -euo pipefail

RG="${RG:-civicspace_group}"
BOT="${BOT:-civic-bot}"
API="2022-09-15"

SUB=$(az account show --query id -o tsv)
URL="https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.BotService/botServices/${BOT}/channels/FacebookChannel/listChannelWithKeys?api-version=${API}"

CHANNEL_JSON="$(az rest --method post --url "$URL" 2>/dev/null || true)"
export CHANNEL_JSON

python3 - <<'PY'
import os, json, datetime, urllib.parse, urllib.request

raw = os.environ.get("CHANNEL_JSON", "")
if not raw.strip():
    print("❌ อ่าน channel จาก Azure ไม่ได้ — ตรวจว่า az login แล้วและมีสิทธิ์เข้าถึง bot")
    raise SystemExit(1)

d = json.loads(raw)
p = d.get("properties", {}).get("properties", {}) or d.get("properties", {})
app_id = str(p.get("appId") or "")
secret = p.get("appSecret") or ""
pages = p.get("pages") or []
if not pages:
    print("❌ ไม่มีเพจผูกกับ channel นี้")
    raise SystemExit(1)
page_id = str(pages[0].get("id") or "")
token = pages[0].get("accessToken") or ""


def graph(path, params):
    url = "https://graph.facebook.com/v21.0/" + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            return None, json.load(e)
        except Exception:
            return None, {"error": {"message": e.read().decode()[:200]}}
    except Exception as e:
        return None, {"error": {"message": str(e)[:200]}}


print("=" * 58)
print("Facebook channel — %s / เพจ %s" % (app_id, page_id))
print("-" * 58)

data, err = graph("debug_token", {
    "input_token": token,
    "access_token": "%s|%s" % (app_id, secret),
})

if err:
    print("❌ App Secret ที่ Azure ถืออยู่ใช้ไม่ได้")
    print("   %s" % err.get("error", {}).get("message", "")[:170])
    print()
    print("   มักเกิดจาก reset App Secret ใน Meta แล้วไม่ได้อัปเดตใน Azure")
    print("   แก้: Azure Bot > Channels > Facebook ใส่ secret + token ตัวใหม่ทั้งคู่")
    raise SystemExit(1)

t = data.get("data", {})
problems = []

print("App Secret        : ✅ ใช้ได้")

ty = t.get("type")
print("ชนิด token         : %s %s" % (ty, "✅" if ty == "PAGE" else "❌ ต้องเป็น PAGE"))
if ty != "PAGE":
    problems.append("token ไม่ใช่ Page token")

prof = str(t.get("profile_id", t.get("user_id", "")))
if prof == page_id:
    print("เป็นของเพจ         : %s ✅" % prof)
else:
    print("เป็นของเพจ         : %s ❌ ต้องเป็น %s" % (prof, page_id))
    problems.append("token เป็นของเพจอื่น")

if t.get("is_valid"):
    print("สถานะ             : valid ✅")
else:
    print("สถานะ             : invalid ❌")
    problems.append("token ไม่ valid")

exp = t.get("expires_at", 0)
if exp == 0:
    print("อายุ token         : ♾️  ไม่มีวันหมดอายุ ✅")
else:
    dt = datetime.datetime.fromtimestamp(exp)
    hrs = (dt - datetime.datetime.now()).total_seconds() / 3600
    if hrs <= 0:
        print("อายุ token         : หมดอายุไปแล้ว %s ❌" % dt.strftime("%Y-%m-%d %H:%M"))
        problems.append("token หมดอายุแล้ว")
    else:
        mark = "✅" if hrs > 168 else "⚠️"
        print("อายุ token         : หมดอายุ %s (อีก %.1f ชม.) %s"
              % (dt.strftime("%Y-%m-%d %H:%M"), hrs, mark))
        if hrs <= 168:
            problems.append("token อายุสั้น (เหลือ %.1f ชม.) ควรแลกเป็น long-lived" % hrs)

scopes = t.get("scopes") or []
if "pages_messaging" in scopes:
    print("pages_messaging   : ✅")
else:
    print("pages_messaging   : ❌ ไม่มี")
    problems.append("ขาด permission pages_messaging")

print("=" * 58)
if problems:
    for x in problems:
        print("⚠️  %s" % x)
    print()
    print("ถ้าเป็นเรื่องอายุ token ให้แลกเป็น long-lived แล้วใส่กลับเข้า Azure:")
    print("  graph.facebook.com/v21.0/oauth/access_token")
    print("    ?grant_type=fb_exchange_token&client_id=<app-id>")
    print("    &client_secret=<app-secret>&fb_exchange_token=<token-เดิม>")
    print("  แล้ว: az bot facebook create -g <rg> -n <bot> --appid .. --page-id .. \\")
    print("          --secret .. --token <ตัวใหม่>")
    raise SystemExit(1)

print("🎉 ปกติทุกอย่าง บอทจะไม่เงียบจากเรื่อง credential")
PY
