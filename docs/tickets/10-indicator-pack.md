# 10: Indicator Pack

**What to build:** โมดูล pure function ที่รับ series ของ candle (OHLCV ตามรูปแบบ Hyperliquid) แล้วคืน Indicator Pack ตาม ADR-0003 และ spec: EMA 20/50, RSI 14, ATR 14 (ราคาและ %), MACD 12/26/9, swing high/low ล่าสุดแบบ fractal 3/3 แต่ละค่าเป็น 3 จุด (ปัจจุบัน, −1, −5 แท่ง) บวกฟังก์ชันต่อ symbol: %change 24h/7d/30d และ anchored VWAP (anchor ที่เวลาใดก็ได้ที่ผู้เรียกกำหนด พร้อม % ระยะห่างและจำนวนแท่งที่สะสม) ทั้งหมดด้วย stdlib มีค่าคงที่ `INDICATOR_PACK_VERSION` และ market source รองรับการดึง ~200 แท่งต่อ timeframe เพื่ออุ่นเครื่อง indicator ก่อนตัดส่งเฉพาะส่วนท้าย ยังไม่ต้องประกอบเข้า prompt (ticket 07)

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] ฟังก์ชัน pack(series) คืน dict ที่มี EMA20, EMA50, RSI14, ATR14 (abs และ pct), MACD (line/signal/hist) แต่ละตัวเป็น 3 จุด (now, -1, -5); swing_high และ swing_low เป็นจุดเดียวต่อฝั่ง (swing ล่าสุดที่ยืนยันแล้ว: price, bars_ago) พร้อม swing_position ค่าเดียว (above/below/between: close ล่าสุดเทียบ swing high และ swing low ล่าสุด) คำนวณจากแท่งที่ปิดแล้วเท่านั้น
- [x] นิยามมาตรฐาน: EMA seed ด้วย SMA, RSI และ ATR แบบ Wilder, MACD 12/26/9, fractal 3 แท่งซ้าย/ขวา ยืนยันแล้วเท่านั้น
- [x] ค่าทุกตัวตรงกับค่าอ้างอิงที่คำนวณครั้งเดียวจาก fixture คงที่ (เช่น ชุด 200 แท่ง BTC ที่บันทึกไว้) ภายใน tolerance 1e-6 สัมพัทธ์
- [x] series สั้นกว่าที่ indicator ต้องการ → ค่านั้นเป็น null ไม่ throw
- [x] pct_change(series, bars) และ vwap(series_15m, anchor_ms) คืนค่าถูกต้องบน fixture รวมกรณี anchor อยู่กลาง series และกรณีไม่มีแท่งหลัง anchor (คืน null + bars=0)
- [x] `INDICATOR_PACK_VERSION` มีค่า และ pack() กับ vwap() แนบ version นี้ (pct_change คืนตัวเลขเดี่ยว ส่วน version ระดับ response บันทึกเป็น `indicator_pack_version` ใน ticket 07 ตาม spec)
- [x] market source ดึง candleSnapshot ได้ถึง 200 แท่งต่อ timeframe ต่อ symbol ใน call เดียว และ replay จาก fixture ได้
- [x] test ด้วย unittest stdlib ไม่เรียก network เป็น seam ที่สอง (pure math) ตามที่ spec อนุญาต
