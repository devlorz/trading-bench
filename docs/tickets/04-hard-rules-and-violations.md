# 04: Hard Rule ครบชุดและ Violation feedback

**What to build:** Engine ตรวจ Action ทุกรายการตามลำดับที่ส่งมา ปฏิเสธรายรายการ (รายการอื่นยัง apply) ตาม Hard Rule ครบชุดใน spec: Slot ว่างและ free equity พอ, symbol อยู่ใน watchlist และ bias ไม่ใช่ avoid, ทิศตรง bias (both = ได้ทั้งคู่), ห้าม long+short สินค้าเดียวกันในบัญชี (ข้าม Layer ก็ไม่ได้), notional ÷ collateral ≤ max leverage, TP อยู่ฝั่งกำไร, slot ที่อ้างมีอยู่จริงและมี position (สำหรับ close/set_tp), response ไม่ตรง schema ถือเป็น hold ทุก Violation บันทึกกฎที่ขัดและ Action ต้นฉบับ และถูกส่งกลับให้ Executor ใน Tick ถัดไป

**Blocked by:** 03 (Settle ย้อนหลังจากแท่ง 1m, ปิดกอง, TP, Hostage)

**Status:** ready-for-agent

- [x] รายการ Action 3 รายการที่รายการกลางขัดกฎ → รายการ 1 และ 3 apply รายการ 2 เป็น Violation
- [x] เปิด ETH short ขณะมี Layer อื่นถือ ETH long → ปฏิเสธด้วยรหัส `opposite_side_open`; เปิด ETH long ซ้ำอีก Layer → ผ่าน
- [x] bias short แต่สั่ง long → ปฏิเสธด้วยรหัส `bias_mismatch`; bias both → ผ่านทั้งคู่; bias avoid → ปฏิเสธ (`bias_mismatch`)
- [x] รหัส Violation ทุกตัวตรงกับที่ระบุในไฟล์สรุปกฎ TSM สำหรับ Executor (ticket 02) คำต่อคำ
- [x] close/set_tp/cancel_tp บน Slot ว่าง → ปฏิเสธ
- [x] response ที่ parse ไม่ได้หรือไม่ตรง schema → บันทึก error, ถือ hold, ไม่นับ Violation
- [x] Violation ทุกรายการมีชื่อกฎ, Action ต้นฉบับ, timestamp และโผล่ใน input ของ Executor Tick ถัดไป
- [x] นับ Violation รวมต่อ Contestant ได้จาก event log
- [x] test ผ่าน seam เดียว ครอบทุกกฎ
