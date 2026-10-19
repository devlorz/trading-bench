# 06: รันหลาย Contestant, Elimination, ตัวชี้วัด และ export ข้อมูล dashboard

**What to build:** คำสั่ง `run-tick` และ `run-week` แบบไม่ระบุ Contestant รันทุกคู่ใน config ตามลำดับ (Hyperliquid ล่มทั้งรอบ → ข้ามทุกคู่เท่ากันและบันทึก) Contestant ที่ equity < 1,000 USDC ถูก Elimination: ปิดสถานะถาวร ไม่เรียกโมเดลอีก คะแนน = equity ตอนนั้น ทุก Tick บันทึก equity snapshot ต่อคู่ และคำนวณตัวชี้วัดตาม spec (Net Return หลัก; Max Drawdown, จำนวน position ปิด, win rate, PnL เฉลี่ยต่อ position, จำนวน liquidation, Violation รวม, fee รวม, funding สุทธิ, จำนวนสัปดาห์ที่ Reallocation เกิด) แล้ว export เป็นชุดไฟล์ JSON สรุปสำหรับ dashboard ที่แยกจาก state ภายใน รวมคำสั่ง `reset` เริ่ม benchmark ใหม่

**Blocked by:** 04 (Hard Rule ครบชุด), 05 (Weekly Plan และ Reallocation)

**Status:** ready-for-agent

- [x] config มีรายการ 6 Contestant ตาม spec (model id ของ Strategist/Executor ต่อคู่) เพิ่ม/ลบคู่ได้โดยไม่แก้โค้ด
- [x] market source ล้มระหว่างรอบ → ไม่มี Contestant ใดถูกประมวลผลใน Tick นั้น และบันทึก Tick ว่า "skipped" พร้อมเหตุผล
- [x] Contestant ที่ equity < 1,000 หลัง settle → สถานะ eliminated พร้อม Week ที่ตกรอบ; Tick/Week ถัดไปไม่เรียกโมเดลของคู่นั้นและ equity หยุดนิ่ง
- [x] ตัวชี้วัดทุกตัวคำนวณจาก event log + equity snapshot ได้ซ้ำแล้วได้ค่าเดิม
- [x] ไฟล์ export มี: leaderboard, equity series ต่อคู่, Layer ปัจจุบัน, position ที่ปิดทั้งหมด, Weekly Plan ทั้งหมด, reasoning ต่อ Tick, Violation, สถานะ Tick ล่าสุด (เวลา, สำเร็จ/ข้าม)
- [x] `reset` ลบ state ทุกคู่แล้วรันใหม่ได้จาก Week 1
- [x] test ผ่าน seam เดียว กับ 2 Contestant จำลอง ครอบ Elimination, skipped Tick และตัวชี้วัด
