#!/usr/bin/env bash
# ใส่ FACEBOOK_PAGE_TOKEN (token อ่านอย่างเดียว) ให้บอทตอบเรื่องโพสต์ล่าสุดของเพจได้
#
#   ./tools/set-page-feed-token.sh
#
# ถาม token แบบไม่แสดงบนจอ → ตรวจกับ Facebook ว่าเป็น PAGE token ของเพจเรา
# และดึงโพสต์ได้จริง → ค่อยใส่เข้า App Settings ของ civic-bot-app
# ไม่พิมพ์ค่า token ออกมาเลย ใช้ซ้ำได้ตอนต่ออายุ token
#
# ต้อง az login ไว้ก่อน

set -euo pipefail

RG="${RG:-civicspace_group}"
APP="${APP:-civic-bot-app}"
PAGE_ID="${PAGE_ID:-728353493701593}"

read -r -s -p "วาง Page Access Token (อ่านอย่างเดียว) แล้วกด Enter: " TOKEN
echo
[ -n "$TOKEN" ] || { echo "❌ ไม่ได้ใส่ token"; exit 1; }
export TOKEN PAGE_ID

python3 - <<'PY'
import os, json, datetime, urllib.parse, urllib.request, urllib.error

token, page_id = os.environ["TOKEN"], os.environ["PAGE_ID"]
G = "https://graph.facebook.com/v21.0/"

def get(path, **params):
    params["access_token"] = token
    try:
        with urllib.request.urlopen(G + path + "?" + urllib.parse.urlencode(params), timeout=20) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            return None, json.load(e)["error"].get("message", "")
        except Exception:
            return None, f"HTTP {e.code}"

d, err = get("debug_token", input_token=token)
if err or not d.get("data", {}).get("is_valid"):
    print(f"❌ token ใช้ไม่ได้ {err or ''}")
    raise SystemExit(1)
d = d["data"]
scopes = d.get("scopes", [])
print(f"  ชนิด: {d.get('type')}   เพจ: {d.get('profile_id')}")
if d.get("type") != "PAGE" or str(d.get("profile_id")) != page_id:
    print(f"❌ ต้องเป็น PAGE token ของเพจ {page_id}")
    raise SystemExit(1)
if "pages_messaging" in scopes:
    print("❌ token นี้มี pages_messaging = token ของ Messenger อย่าใช้ซ้ำ ให้ใช้ token อ่านอย่างเดียว")
    raise SystemExit(1)
exp = d.get("data_access_expires_at")
if exp:
    when = datetime.datetime.fromtimestamp(exp, datetime.timezone.utc)
    days = (when - datetime.datetime.now(datetime.timezone.utc)).days
    print(f"  data access หมดอายุ: {when:%d %b %Y} (อีก {days} วัน)")

posts, err = get(f"{page_id}/posts", fields="created_time,message", limit=1)
if err:
    print(f"❌ ดึงโพสต์ไม่ได้: {err}")
    raise SystemExit(1)
latest = (posts.get("data") or [{}])[0]
print(f"  ✅ ดึงโพสต์ได้ — ล่าสุด {latest.get('created_time', '?')}: "
      f"{(latest.get('message') or '(ไม่มีข้อความ)').splitlines()[0][:60]}")
PY

az webapp config appsettings set -g "$RG" -n "$APP" -o none \
  --settings FACEBOOK_PAGE_ID="$PAGE_ID" FACEBOOK_PAGE_TOKEN="$TOKEN"
echo "✅ ใส่ FACEBOOK_PAGE_TOKEN ใน $APP แล้ว (แอปจะรีสตาร์ทเอง ~1 นาที)"
