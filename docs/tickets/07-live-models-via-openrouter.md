# 07: เรียกโมเดลจริงผ่าน OpenRouter และประกอบ prompt

**What to build:** model client ตัวจริงที่เรียก OpenRouter ด้วย model id จาก config, บังคับ JSON output ตาม schema ของ Executor (reasoning + Action list) และ Strategist (Weekly Plan), temperature default ของค่าย ไม่มี tool; client **ไม่ retry เอง**: หน้าที่มีแค่เรียก OpenRouter แล้ว parse JSON และ raise exception ใดก็ได้เมื่อล้ม เพราะ Engine (ticket 04) เป็นคน retry และ validate schema อยู่แล้ว โดยส่ง error ของครั้งก่อนมาใน key `retry_error` ของ request ซึ่ง prompt ต้องแสดงให้โมเดลเห็น ประกอบ prompt ของ Executor ตาม spec (สรุปกฎ TSM ฉบับย่อจาก ticket 02 พร้อม hash, Weekly Plan, สถานะบัญชี/Layer/liq price, event ที่ settle, Violation ก่อนหน้า, log สัปดาห์นี้, candle 4H × 30 / 1H × 24 / 15m × 16 ต่อ symbol พร้อม Indicator Pack จาก ticket 10, %change, daily VWAP, mark, funding, OI, max leverage) และของ Strategist (รวม TSM เต็มฉบับ) ทุกการเรียกบันทึก response ดิบ + snapshot id ของข้อมูลตลาด + hash ของสรุป TSM ลง repo และเขียน prompt ดิบลงโฟลเดอร์ artifact ให้ workflow อัปโหลด

**Blocked by:** 02 (สรุปกฎ TSM ฉบับย่อ), 04 (Hard Rule ครบชุด), 05 (Weekly Plan และ Reallocation), 10 (Indicator Pack)

**Status:** ready-for-agent

- [ ] รัน `run-tick` จริงกับ Contestant เดียวด้วย OpenRouter key แล้วได้ Action ที่ parse ผ่านและ apply ได้ (ทดสอบด้วยมือหนึ่งครั้งต่อค่ายทั้ง 6 คู่ บันทึกผลใน ticket)
- [ ] client ล้ม (network, timeout, JSON พัง) → raise ออกมาให้ Engine จัดการ ไม่ retry เอง ไม่กลืน exception
- [ ] เมื่อ request มี `retry_error` prompt แสดง error นั้นให้โมเดลเห็นก่อนตอบใหม่ (ตรวจด้วย test ว่า prompt ที่ประกอบมีข้อความ error)
- [ ] prompt ของ Executor สำหรับ watchlist 5 ตัวมีขนาดไม่เกิน ~30k token และไม่มีข้อมูลสินค้านอก watchlist
- [ ] ทุก response บันทึก `indicator_pack_version` คู่กับ hash ของสรุป TSM
- [ ] prompt ของ Strategist มี TSM เต็มฉบับ, แผนและทุกไม้สัปดาห์ก่อนพร้อม reasoning, และข้อมูล universe ตาม spec
- [ ] TSM เต็มฉบับ**ไม่อยู่ใน repo** (เป็นเนื้อหาของผู้อื่น repo เป็น public): Engine อ่านจาก path ใน env var `TSM_FULL_PATH` ถ้าไม่ตั้งหรือไฟล์ไม่มี → run-week ล้มด้วย error ที่บอกชื่อ env var ไม่ใช่ fallback เงียบ; path นั้นและชื่อไฟล์ที่น่าจะใช้อยู่ใน `.gitignore`; ทุก response ของ Strategist บันทึก sha256 ของไฟล์ที่อ่านได้จริง
- [ ] test ประกอบ prompt ของ Strategist ใช้ไฟล์ TSM ปลอมสั้นๆ ใน fixture ไม่ใช่ไฟล์จริง
- [ ] ทุก response เก็บถาวรพร้อม model id, snapshot id, hash สรุป TSM, token usage และ latency
- [ ] prompt ดิบถูกเขียนลงโฟลเดอร์ artifact ที่ไม่ถูก commit
- [ ] test: model client จำลอง HTTP ล้ม/ตอบพัง ผ่าน seam เดียว ไม่เรียก network
