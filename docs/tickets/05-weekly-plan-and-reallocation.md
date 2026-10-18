# 05: Weekly Plan จาก Strategist และ Reallocation

**What to build:** คำสั่ง `run-week --contestant X --at <monday>` ที่ settle ชั่วโมงค้าง → ตัดสินว่าจะ Reallocation ไหม (เฉพาะเมื่อทุก Layer ว่าง) → เรียก Strategist ผ่าน model client ที่ฉีดได้ด้วย input ตาม spec (TSM เต็มฉบับ, แผนและทุกไม้ของสัปดาห์ก่อนพร้อม reasoning ของ Executor, Violation, สถานะบัญชีและผล Reallocation ที่จะเกิด, universe top 50 ตาม 24h volume พร้อม daily × 60 / weekly × 26 candles, funding เฉลี่ย 7 วัน, OI, max leverage, รายชื่อ symbol ทั้งหมด) → validate แผน (symbol มีจริง, watchlist ≤ 5, notional ≥ 10 USD, notional ÷ collateral ที่จะใช้จริง ≤ max leverage ทุก symbol) → retry พร้อม error ได้ 2 ครั้ง → fallback แผนเดิม (Week แรกไม่มีแผน = hold ทั้งสัปดาห์ + 1 Violation) → บันทึกแผนและ apply RP ใหม่เฉพาะเมื่อ Reallocation เกิด Tick ต่อจากนั้นใช้แผนล่าสุดที่บันทึก

**Blocked by:** 03 (Settle ย้อนหลังจากแท่ง 1m, ปิดกอง, TP, Hostage)

**Status:** ready-for-agent

- [ ] ทุก Layer ว่างที่ขอบ Week → collateral ใหม่ = equity ÷ 4 และ notional จากแผนใหม่ถูกใช้
- [ ] มี Layer ค้างที่ขอบ Week → RP เดิมใช้ต่อ notional ใหม่ถูกบันทึกว่า "ไม่ถูกใช้" ไม่นับ Violation และ Strategist ได้รับแจ้งล่วงหน้าใน input ว่า Reallocation จะไม่เกิด
- [ ] แผนที่ notional เกิน leverage ของ symbol ใด → error กลับ Strategist ที่ระบุ symbol และเพดาน → แผนที่แก้ในรอบ 2 ผ่าน
- [ ] ล้ม 3 ครั้ง → ใช้แผนสัปดาห์ก่อนทั้งฉบับ; Week แรกล้ม 3 ครั้ง → Executor hold ทุก Tick ของสัปดาห์และมี Violation 1 รายการ
- [ ] Strategist เลือก symbol นอก top 50 ที่มีบน Hyperliquid ได้
- [ ] แผนทุกสัปดาห์ถูกเก็บถาวรพร้อม rationale และตรวจย้อนได้ว่า Tick ใดใช้แผนใด
- [ ] test ผ่าน seam เดียว ด้วย Strategist ที่สคริปต์ไว้ ครอบทุกข้อ
