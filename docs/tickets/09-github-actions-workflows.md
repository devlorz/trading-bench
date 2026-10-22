# 09: GitHub Actions workflow รายชั่วโมง/รายสัปดาห์ และ GitHub Pages

**What to build:** repo public บน GitHub พร้อม workflow เดียวตาม ADR-0002: cron รายชั่วโมง (`7 * * * *`) job เดียวรัน `run-week` (idempotent ต่อ Week ทำงานจริงเฉพาะรอบแรกหลังจันทร์ 00:00 UTC และต้องไม่เขียนอะไรเมื่อถูกข้าม) แล้วต่อด้วย `run-tick` ทุก Contestant ใช้ concurrency group กันรันซ้อน, อ่าน OpenRouter key จาก Secrets, commit state และไฟล์ export กลับเข้า main, อัปโหลดโฟลเดอร์ prompt ดิบเป็น artifact (90 วัน), เปิด GitHub Pages จาก main ให้ dashboard จาก ticket 08 ออนไลน์ รวม README วิธีรันด้วยมือ (fixture และ live), วิธี reset และวิธีเริ่ม Week 1

**Blocked by:** 06 (รันหลาย Contestant), 07 (เรียกโมเดลจริง), 08 (Dashboard)

**Status:** ready-for-agent

- [ ] trigger ด้วยมือ (workflow_dispatch) แล้ว Tick รันสำเร็จ commit ไฟล์ state/export กลับ และ dashboard บน Pages อัปเดต
- [ ] workflow ซ้อนกันไม่ได้ (รอบที่สองรอรอบแรก) และ Tick ที่ดีเลย์ settle ช่วงที่หายถูกต้อง
- [ ] prompt ดิบปรากฏเป็น artifact ของ run และไม่อยู่ใน commit
- [ ] TSM เต็มฉบับมาจาก GitHub Secret `TSM_FULL_B64` (gzip -9 แล้ว base64 ไฟล์จริง ~25KB เข้าเพดาน 48KB) workflow ถอดลงไฟล์ชั่วคราวนอก working tree แล้วส่ง path ผ่าน `TSM_FULL_PATH` ให้ Engine; ไฟล์นั้นไม่ถูก commit ไม่ถูกอัปโหลดเป็น artifact และไม่ถูก echo ลง log; README มีคำสั่งสร้าง secret จากไฟล์ใน Obsidian และบอกว่าทำไมไม่อยู่ใน repo
- [x] Hyperliquid ล้มใน run → run จบแบบสำเร็จแต่บันทึก Tick ว่า skipped (ไม่ส่ง failure email ถล่ม)
- [x] `run-week` ล้มกลางคัน → รอบชั่วโมงถัดไปสร้างแผนของ Week นั้นให้ (idempotent) และ Tick ระหว่างนั้นใช้แผนล่าสุดโดยไม่พัง; รอบที่ `run-week` ถูกข้ามต้องไม่มี commit เพิ่มจากขั้นนั้น
- [x] README อธิบายรันด้วยมือ, reset, เริ่ม Week 1 และเพิ่ม Contestant ผ่าน config
- [ ] Week 1 เริ่มจริงและ Tick แรกของทั้ง 6 คู่ปรากฏบน dashboard
