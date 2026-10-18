# 03: Settle ย้อนหลังจากแท่ง 1m, ปิดกอง, TP, Hostage

**What to build:** เมื่อ `run-tick` รัน ณ เวลาใด Engine ต้อง settle ทุกอย่างที่เกิดตั้งแต่ Tick ก่อนหน้าโดยไล่แท่ง 1m ตามเวลา: funding ทุกชั่วโมงเต็มหักจาก collateral ของ Layer ที่ถือ, TP fill ด้วย maker fee ที่ราคา TP เมื่อแท่งแตะ, liquidation ทั้งกองเมื่อ layer equity ≤ maintenance (notional ÷ (2 × max leverage)) โดยใช้ high/low ของแท่งเป็น mark ที่เลวร้ายสุด และ liquidation ชนะ TP ในแท่งเดียวกัน ทุก event มี timestamp ของแท่ง จากนั้น Executor สั่ง `close` (market, taker fee), `set_tp`, `cancel_tp` ได้ การปิดกองคืน collateral ± PnL เข้า free equity ส่วนเกินทุนเดิมคือ Hostage และเปิด Slot ที่ถูก liquidate ใหม่ได้เมื่อ free equity ≥ collateral ถ้าช่วงที่หายยาวกว่าที่ 1m ดึงได้ ถอยไป 15m แล้ว 1H และบันทึกความละเอียดที่ใช้

**Note (ผลจาก fee ตอน open หักจาก collateral ของ Layer, ดู spec "โมเดล Layer"):** liquidation threshold ของกองเริ่มจาก collateral หลังหัก fee (เช่น 2,500 − 4.5 = 2,495.5) ไม่ใช่ 2,500; Hostage ตอนปิดกองคือส่วนที่เกิน collateral ใน RP (2,500) ไม่ใช่เกิน 2,495.5

**Blocked by:** 01 (รัน Tick เดียวแล้วเปิด Layer ได้)

**Status:** ready-for-agent

- [ ] Tick ที่ห่างจาก Tick ก่อน 3 ชั่วโมง settle funding 3 ครั้งด้วย rate จริงของแต่ละชั่วโมงจาก funding history
- [ ] TP fill กลางชั่วโมงบันทึก timestamp ของแท่ง 1m นั้น คิด maker fee 0.015% และ Slot ว่างก่อน Executor ตัดสินใจ
- [ ] Layer ถูก liquidate เมื่อแท่ง 1m ทำให้ layer equity ≤ maintenance รวมกรณีที่ funding สะสมเป็นตัวดันให้ถึง collateral ที่เหลือ = 0
- [ ] แท่งเดียวกันเข้าทั้ง TP และ liquidation → liquidation ชนะ
- [ ] `close` คืน collateral ± PnL − fee เข้า free equity; `set_tp` แทนที่ TP เดิม; `cancel_tp` ลบ; TP ฝั่งผิดของ entry ถูกปฏิเสธ
- [ ] หลัง liquidate 1 กอง เปิด Slot นั้นใหม่ไม่ได้จน free equity ≥ collateral แล้วเปิดได้
- [ ] Executor เห็น event ที่ settle ไปตั้งแต่ Tick ก่อนใน input ของ Tick นี้
- [ ] ช่วงที่หายเกินขีดจำกัด 1m ใช้ 15m/1H และ event บันทึกว่าใช้ความละเอียดใด
- [ ] test ผ่าน seam เดียวกับ 01 ครอบทุกข้อ ไม่เรียก network
