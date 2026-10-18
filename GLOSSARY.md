# Trading Bench

Benchmark เปรียบเทียบ AI model ด้วยการ paper-trade perpetual futures บน Hyperliquid แบบสองชั้น (วางแผนรายสัปดาห์ → ลงมือรายชั่วโมง) ภายใต้กรอบทรัพยากรของ TSM Principle 4 (Hostage Hunt)

## Language

### ผู้เล่น

**Contestant**:
หน่วยที่ถูกจัดอันดับ คือคู่ Strategist + Executor จากค่ายเดียวกัน หนึ่ง Contestant มีหนึ่ง Paper Account
_Avoid_: team, bot, agent

**Strategist**:
โมเดลตัวหลักของ Contestant ที่ออก Weekly Plan หนึ่งครั้งต่อสัปดาห์
_Avoid_: planner, big model, brain

**Executor**:
โมเดลตัวเล็กของ Contestant ที่ตัดสินใจ Action ทุก Tick ภายในกรอบ Weekly Plan
_Avoid_: trader, small model, worker

**Engine**:
โค้ดที่จำลองตลาด บังคับ Hard Rule และบันทึกผล ไม่ตัดสินใจเทรดเอง
_Avoid_: simulator, backend

### จังหวะเวลา

**Week**:
รอบวางแผน เริ่มจันทร์ 00:00 UTC ถึงจันทร์ถัดไป
_Avoid_: round, epoch

**Tick**:
รอบตัดสินใจรายชั่วโมงของ Executor
_Avoid_: step, cycle, hour

**Weekly Plan**:
ผลลัพธ์ของ Strategist หนึ่งสัปดาห์: โครงสร้างข้อมูล (watchlist, bias, เงื่อนไข entry/exit, เงื่อนไขปิดทุกกอง, Risk Parameter) บวก rationale เป็นข้อความ
_Avoid_: strategy, playbook

**Action**:
คำสั่งหนึ่งรายการที่ Executor ส่งให้ Engine ใน Tick (เปิด/ปิด Layer, ตั้ง TP, hold)
_Avoid_: order, trade, decision

### ทุนและความเสี่ยง (TSM)

**Paper Account**:
บัญชีจำลองของ Contestant เริ่มที่ 10,000 USDC ไม่เติมทุน
_Avoid_: wallet, portfolio

**Layer**:
กองทัพย่อยตาม TSM บัญชีย่อยที่ถือ collateral หนึ่งในสี่ของทุน ณ Reallocation ล่าสุด และถือ position ได้ครั้งละหนึ่งตัว ถูก liquidate ทั้งกองเมื่อ collateral หมด มีสี่ Layer เสมอ
_Avoid_: slot, army, sub-account, bucket

**Slot**:
ที่ว่างสำหรับ Layer หนึ่งในสี่ ที่ว่างอยู่เมื่อ Layer ปิดหรือถูก liquidate
_Avoid_: empty layer

**Risk Parameter (RP)**:
collateral ต่อ Layer และขนาด position (notional) ที่เท่ากันทุก Layer และเปลี่ยนได้เฉพาะตอน Reallocation ไม่รวม leverage ซึ่งเป็นแค่ผลลัพธ์
_Avoid_: risk setting, sizing, leverage

**Reallocation**:
การใช้ RP ใหม่จาก Weekly Plan เกิดเฉพาะที่ขอบ Week และเฉพาะเมื่อไม่มี Layer ใดถือ position อยู่ ไม่เช่นนั้น RP เดิมใช้ต่อทั้งสัปดาห์
_Avoid_: rebalance, resize

**Hostage**:
กำไรที่ Layer ปิดได้แล้วและสะสมอยู่ในบัญชี ตาม TSM เรียก "เชลย"
_Avoid_: buffer, profit, PnL

**Hard Rule**:
กฎ TSM ที่ Engine ตรวจและปฏิเสธ Action ได้ด้วยโค้ด
_Avoid_: constraint, guard

**Soft Rule**:
กฎ TSM เชิงคุณภาพที่ใส่ใน prompt แต่ Engine ตรวจไม่ได้
_Avoid_: guideline, hint

**Violation**:
Action ที่ Engine ปฏิเสธเพราะขัด Hard Rule หรือ Weekly Plan นับเป็นตัวชี้วัดรอง
_Avoid_: error, rejection

### การวัดผล

**Net Return**:
ตัวชี้วัดหลัก คือ equity สุดท้าย (รวม unrealized, หักค่าธรรมเนียมและ funding) เทียบทุนเริ่มต้น
_Avoid_: PnL, profit, score

**Elimination**:
สถานะ Contestant เมื่อ equity ต่ำกว่า 1,000 USDC หยุดเทรดและใช้ equity นั้นเป็นคะแนนสุดท้าย
_Avoid_: bust, liquidation (คำนี้สงวนไว้สำหรับ position)
