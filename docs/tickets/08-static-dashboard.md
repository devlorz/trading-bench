# 08: Dashboard แบบ static บน GitHub Pages

**What to build:** เว็บ static (HTML + Chart.js จาก CDN ไม่มี build step ไม่มี backend) ที่อ่านไฟล์ export จาก ticket 06 แล้วแสดง: หน้าแรก = leaderboard จัดอันดับด้วย Net Return พร้อมตัวชี้วัดรอง และ equity curve ทุก Contestant ซ้อนกัน, สถานะ Tick ล่าสุดและว่าสำเร็จ/ข้าม, เครื่องหมาย Elimination; หน้าต่อ Contestant = Layer ที่เปิด (symbol ทิศ notional entry mark PnL liq TP), ประวัติ position ปิด (เวลาเปิด/ปิด ราคา fee funding PnL เหตุผลปิด), Weekly Plan ทุกสัปดาห์พร้อม rationale, reasoning ของ Executor ทุก Tick คู่กับ Action, รายการ Violation ใช้งานได้บนมือถือ

**Blocked by:** 06 (รันหลาย Contestant, Elimination, ตัวชี้วัด และ export)

**Status:** ready-for-agent

- [ ] เปิดจากไฟล์ export ตัวอย่างที่ test ของ ticket 06 ผลิต แล้วทุกหน้าตาม spec แสดงครบ
- [ ] leaderboard เรียงตาม Net Return และแสดง Contestant ที่ eliminated พร้อมสัปดาห์ที่ตกรอบ
- [ ] equity chart ซ้อน 6 เส้น เลือกซ่อน/แสดงรายคู่ได้
- [ ] หน้ารายคู่เปิดจาก leaderboard และแสดง 5 ส่วนตาม spec
- [ ] ใช้งานได้ที่ความกว้าง 375px ไม่มี horizontal scroll
- [ ] ตรวจด้วยตาจากไฟล์ตัวอย่าง ไม่มี automated test
