# 09: GitHub Actions workflow รายชั่วโมง/รายสัปดาห์ และ GitHub Pages

**What to build:** repo public บน GitHub พร้อม workflow สองตัวตาม ADR-0002: hourly (`7 * * * *`) รัน `run-tick` ทุก Contestant, weekly (จันทร์ 00:07 UTC) รัน `run-week` ทั้งคู่ใช้ concurrency group เดียวกัน, อ่าน OpenRouter key จาก Secrets, commit state และไฟล์ export กลับเข้า main, อัปโหลดโฟลเดอร์ prompt ดิบเป็น artifact (90 วัน), เปิด GitHub Pages จาก main ให้ dashboard จาก ticket 08 ออนไลน์ รวม README วิธีรันด้วยมือ (fixture และ live), วิธี reset และวิธีเริ่ม Week 1

**Blocked by:** 06 (รันหลาย Contestant), 07 (เรียกโมเดลจริง), 08 (Dashboard)

**Status:** ready-for-agent

- [ ] trigger ด้วยมือ (workflow_dispatch) แล้ว Tick รันสำเร็จ commit ไฟล์ state/export กลับ และ dashboard บน Pages อัปเดต
- [ ] workflow ซ้อนกันไม่ได้ (รอบที่สองรอรอบแรก) และ Tick ที่ดีเลย์ settle ช่วงที่หายถูกต้อง
- [ ] prompt ดิบปรากฏเป็น artifact ของ run และไม่อยู่ใน commit
- [ ] Hyperliquid ล้มใน run → run จบแบบสำเร็จแต่บันทึก Tick ว่า skipped (ไม่ส่ง failure email ถล่ม)
- [ ] weekly run ล้มกลางคัน → hourly run ถัดไปยังใช้แผนล่าสุดและไม่พัง
- [ ] README อธิบายรันด้วยมือ, reset, เริ่ม Week 1 และเพิ่ม Contestant ผ่าน config
- [ ] Week 1 เริ่มจริงและ Tick แรกของทั้ง 6 คู่ปรากฏบน dashboard
