# 01: รัน Tick เดียวแล้วเปิด Layer ได้ (tracer bullet)

**What to build:** คำสั่ง CLI `run-tick` สำหรับ Contestant เดียว ที่รับ market source และ model client ที่ฉีดได้ (seam เดียวตาม spec) เมื่อฉีด fixture ตลาดจากไฟล์ + Weekly Plan ที่เขียนมือ + response ของ Executor ที่สคริปต์ไว้ว่า `open` BTC long ใน slot 0 ระบบต้องสร้าง Paper Account 10,000 USDC, Reallocation ครั้งแรก (4 Layer collateral 2,500), fill ที่ best ask จาก L2 พร้อม taker fee, ล็อก collateral เข้า Layer, บันทึก state เป็น JSON และ event log แล้วรันซ้ำอีก Tick ด้วย `hold` state ต้องไม่เปลี่ยน รวม market source ตัวจริงที่ดึงจาก Hyperliquid public API พร้อมโหมด `record` เพื่อผลิต fixture

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `run-tick --contestant X --at <iso>` รันได้ทั้งกับ market source แบบ fixture และแบบ live Hyperliquid (meta/asset ctxs, L2, candles, funding history)
- [ ] โหมด record บันทึก response ของ Hyperliquid ลงโฟลเดอร์ fixture แล้วโหมด replay ให้ผลเหมือนกันทุก byte ของ state
- [ ] Tick แรกสร้างบัญชี 10,000 USDC และ Reallocation เป็น 4 Layer collateral 2,500 ตาม notional ใน Weekly Plan
- [ ] Action `open` fill ที่ best ask/bid จาก L2, คิด taker fee 0.045% จาก config, free equity ลด 2,500, Layer บันทึก symbol/side/notional/entry/collateral
- [ ] `open` ถูกปฏิเสธเมื่อไม่มี Slot ว่าง, free equity < collateral, symbol ไม่อยู่ใน watchlist หรือ notional ÷ collateral > max leverage ของ symbol และบันทึกเป็น Violation
- [ ] `hold` ไม่เปลี่ยน state; รัน Tick เดิมซ้ำสองครั้งให้ event log ไม่ซ้ำ (idempotent ต่อ timestamp)
- [ ] State และ event log เป็น JSON อ่านได้ แยกโฟลเดอร์ต่อ Contestant
- [ ] มี test ผ่าน seam นี้ด้วย unittest stdlib ครอบทุกข้อข้างบน ไม่เรียก network
