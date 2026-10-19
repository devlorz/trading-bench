# 08: Dashboard แบบ static บน GitHub Pages

**What to build:** เว็บ static (HTML + Chart.js จาก CDN ไม่มี build step ไม่มี backend) ที่อ่านไฟล์ export จาก ticket 06 แล้วแสดง: หน้าแรก = leaderboard จัดอันดับด้วย Net Return พร้อมตัวชี้วัดรอง และ equity curve ทุก Contestant ซ้อนกัน, สถานะ Tick ล่าสุดและว่าสำเร็จ/ข้าม, เครื่องหมาย Elimination; หน้าต่อ Contestant = Layer ที่เปิด (symbol ทิศ notional entry mark PnL liq TP), ประวัติ position ปิด (เวลาเปิด/ปิด ราคา fee funding PnL เหตุผลปิด), Weekly Plan ทุกสัปดาห์พร้อม rationale, reasoning ของ Executor ทุก Tick คู่กับ Action, รายการ Violation ใช้งานได้บนมือถือ

**Blocked by:** 06 (รันหลาย Contestant, Elimination, ตัวชี้วัด และ export)

**Status:** ready-for-agent

- [x] เปิดจากไฟล์ export ตัวอย่างที่ test ของ ticket 06 ผลิต แล้วทุกหน้าตาม spec แสดงครบ
- [x] leaderboard เรียงตาม Net Return และแสดง Contestant ที่ eliminated พร้อมสัปดาห์ที่ตกรอบ
- [x] equity chart ซ้อน 6 เส้น เลือกซ่อน/แสดงรายคู่ได้
- [x] หน้ารายคู่เปิดจาก leaderboard และแสดง 5 ส่วนตาม spec
- [x] ใช้งานได้ที่ความกว้าง 375px ไม่มี horizontal scroll
- [x] ตรวจด้วยตาจากไฟล์ตัวอย่าง ไม่มี automated test

หมายเหตุ: ไฟล์ตัวอย่างใช้ `python3 -m tests.sample_site` (ขับ Engine ผ่าน seam เดียวกับ test) แทน export จาก test ของ 06 ซึ่งมีแค่ 2 Contestant ไม่พอเช็คกราฟหลายเส้น TP/liquidation/Elimination ที่ยังถือ Layer, fallback plan, Week 1 ไม่มีแผน, Contestant ที่เข้ากลางทาง และ Tick ที่ถูกข้าม
