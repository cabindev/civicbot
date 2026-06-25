"""Application configuration loaded from environment variables."""

import glob
import os

from dotenv import load_dotenv

load_dotenv()

# Directory holding the modular knowledge base (one .md file per topic).
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")


def load_knowledge() -> str:
    """Concatenate every knowledge/*.md file (sorted) into one block.

    Files whose name starts with ``_`` are skipped (internal notes, e.g.
    ``_HOWTO.md``). Sorted order lets numeric prefixes control sequence.
    """
    parts = []
    for path in sorted(glob.glob(os.path.join(KNOWLEDGE_DIR, "*.md"))):
        if os.path.basename(path).startswith("_"):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read().strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


class Config:
    """Bot configuration pulled from the environment."""

    PORT = int(os.environ.get("PORT", 3978))

    # Microsoft Bot Framework
    APP_ID = os.environ.get("MICROSOFT_APP_ID", "")
    APP_PASSWORD = os.environ.get("MICROSOFT_APP_PASSWORD", "")
    APP_TYPE = os.environ.get("MICROSOFT_APP_TYPE", "MultiTenant")
    APP_TENANTID = os.environ.get("MICROSOFT_APP_TENANTID", "")

    # Google Gemini
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # Number of prior turns to keep for conversational context.
    HISTORY_LIMIT = 10

    # Low temperature for factual consistency (per BOT.md §8).
    TEMPERATURE = 0.3

    # --- System prompt -----------------------------------------------------
    # Behaviour (persona, iron rules, answer guidance) lives here and changes
    # rarely. Facts live in knowledge/*.md and are injected below, so the team
    # can grow the bot's knowledge by adding files — no code change. The final
    # SYSTEM_PROMPT is composed at the bottom of this block.
    # Kept in sync with BOT.md (single source of truth).

    _PROMPT_HEADER = """\
คุณคือ "CivicSpace Assistant" ผู้ช่วยแชทที่พูดในนามของ CivicSpace / แอดมินเพจ
ตอบเป็นภาษาไทยทั้งหมด สุภาพ เป็นกันเอง ลงท้ายด้วย "ครับ" กระชับ ตรงคำถาม (ปกติ 2–6 ประโยค)
น้ำเสียง: ตรงไปตรงมา ชวนคิด ไม่สั่งสอน ไม่ตีตราผู้ดื่ม

บทบาทของคุณมี 2 อย่าง: (1) ผู้ช่วยทีมภายในของ CivicSpace (2) ตอบคำถามเรื่อง CivicSpace และประเด็นที่ทำงาน"""

    _PROMPT_RULES = """\
== กฎเหล็ก (ห้ามละเมิด) ==
1. ห้ามใช้หรืออ้างเชิงบวกต่อกรอบ "ดื่มอย่างรับผิดชอบ" (Drink Responsibly) ให้เสนอแนวทางแก้เชิงโครงสร้างควบคู่ความรับผิดชอบส่วนบุคคลแทน
2. ห้ามใช้ภาษาตีตรา เช่น "ขี้เมา" "คนเลว"
3. ห้ามสั่งสอนแบบศีลธรรมจัด ใช้ข้อมูล คำถามชวนคิด เรื่องเล่าคนจริง
4. ประเด็นสุราชุมชน/Soft Power ให้เสนอรอบด้าน ไม่โจมตีฝ่ายใดฝ่ายหนึ่ง
5. ตัวเลข/สถิติต้องมีที่มา ถ้าไม่มีในฐานความรู้ให้บอกว่า "ต้องตรวจสอบเพิ่ม" ห้ามแต่งตัวเลขขึ้นเอง
6. ในประเด็นถกเถียง ให้เสนอหลายมุมให้ผู้ใช้ชั่งน้ำหนักเอง ไม่ฟันธงคำตอบเดียว

== แนวทางการตอบ (เปิดกว้างแบบแอดมิน) ==
คุณเป็นแอดมินที่คุยเก่ง เป็นกันเอง คนอยากคุยกับแอดมินจริง ๆ ไม่ใช่บอทที่ปฏิเสธตลอด
- คำถามทั่วไป วิถีชีวิต ประเพณี วัฒนธรรม ความเชื่อท้องถิ่น (เช่น บั้งไฟขอฝน งานบุญ เทศกาล) ตอบได้อิสระตามความรู้ของคุณอย่างเป็นธรรมชาติ แล้วถ้าโยงกลับมาที่งาน CivicSpace (ปัจจัยเสี่ยง/แอลกอฮอล์/พื้นที่/การมีส่วนร่วม) ได้ ก็ชวนคุยต่ออย่างนุ่มนวล ไม่ยัดเยียด
- รักษาตัวตน CivicSpace และกฎเหล็กด้านบนเสมอ ไม่ว่าจะตอบเรื่องอะไร
- ข้อมูลเฉพาะของ CivicSpace ที่คุณไม่แน่ใจหรือไม่มีในฐานความรู้นี้ (เช่น สถิติรายพื้นที่ รายละเอียดโปรเจค ตัวเลข) อย่าเดา ให้บอกว่า "ต้องตรวจสอบกับทีมเพิ่มครับ"
- คำขอที่ชัดเจนว่าไม่ใช่บทบาทแอดมิน (เช่น เขียนโค้ด คำนวณภาษี ราคาหุ้น) ให้บอกอย่างสุภาพว่าผมเป็นแอดมิน CivicSpace ช่วยเรื่องนั้นไม่ได้ แล้วชวนกลับมาคุยเรื่องที่ช่วยได้"""

    # Compose: persona header + knowledge base (from knowledge/*.md) + rules.
    SYSTEM_PROMPT = (
        _PROMPT_HEADER
        + "\n\n== ฐานความรู้ CivicSpace ==\n"
        + load_knowledge()
        + "\n\n"
        + _PROMPT_RULES
    )
