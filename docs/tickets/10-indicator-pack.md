# 10: Indicator Pack

**What to build:** โมดูล pure function ที่รับ series ของ candle (OHLCV ตามรูปแบบ Hyperliquid) แล้วคืน Indicator Pack ตาม ADR-0003 และ spec: EMA 20/50, RSI 14, ATR 14 (ราคาและ %), MACD 12/26/9, swing high/low ล่าสุดแบบ fractal 3/3 แต่ละค่าเป็น 3 จุด (ปัจจุบัน, −1, −5 แท่ง) บวกฟังก์ชันต่อ symbol: %change 24h/7d/30d และ anchored VWAP (anchor ที่เวลาใดก็ได้ที่ผู้เรียกกำหนด พร้อม % ระยะห่างและจำนวนแท่งที่สะสม) ทั้งหมดด้วย stdlib มีค่าคงที่ `INDICATOR_PACK_VERSION` และ market source รองรับการดึง ~200 แท่งต่อ timeframe เพื่ออุ่นเครื่อง indicator ก่อนตัดส่งเฉพาะส่วนท้าย ยังไม่ต้องประกอบเข้า prompt (ticket 07)

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] ฟังก์ชัน pack(series) คืน dict ที่มี EMA20, EMA50, RSI14, ATR14 (abs และ pct), MACD (line/signal/hist), swing_high, swing_low แต่ละตัวเป็น 3 จุด (now, -1, -5) และ swing มี price, bars_ago, position (above/below/between)
- [ ] นิยามมาตรฐาน: EMA seed ด้วย SMA, RSI และ ATR แบบ Wilder, MACD 12/26/9, fractal 3 แท่งซ้าย/ขวา ยืนยันแล้วเท่านั้น
- [ ] ค่าทุกตัวตรงกับค่าอ้างอิงที่คำนวณครั้งเดียวจาก fixture คงที่ (เช่น ชุด 200 แท่ง BTC ที่บันทึกไว้) ภายใน tolerance 1e-6 สัมพัทธ์
- [ ] series สั้นกว่าที่ indicator ต้องการ → ค่านั้นเป็น null ไม่ throw
- [ ] pct_change(series, bars) และ vwap(series_15m, anchor_ms) คืนค่าถูกต้องบน fixture รวมกรณี anchor อยู่กลาง series และกรณีไม่มีแท่งหลัง anchor (คืน null + bars=0)
- [ ] `INDICATOR_PACK_VERSION` มีค่าและทุกผลลัพธ์แนบ version นี้
- [ ] market source ดึง candleSnapshot ได้ถึง 200 แท่งต่อ timeframe ต่อ symbol ใน call เดียว และ replay จาก fixture ได้
- [ ] test ด้วย unittest stdlib ไม่เรียก network เป็น seam ที่สอง (pure math) ตามที่ spec อนุญาต
