version: 1

# กฎ TSM Principle 4 (Hostage Hunt)

## 1. กลไกบัญชีและตำแหน่ง

- **Layer**: มี 4 Layer เสมอ แต่ละ Layer ถือ `collateral` 1/4 ของทุน ณ Reallocation ล่าสุด และถือ `position` ได้ครั้งละ 1 ตัวตาม RP (ไม่มี scale-in/partial close)
- **Slot** (`0..3`): ที่ว่างสำหรับแต่ละ Layer (ว่างเมื่อปิดหรือถูก liquidate)
- **RP & Reallocation**: `RP = { collateral, notional }` เท่ากันทุก Layer และคงที่ทั้ง Week **Reallocation** อัปเดต RP (`collateral = equity ÷ 4`, `notional` ใหม่) เฉพาะขอบ Week (จันทร์ 00:00 UTC) เมื่อทุก Slot ว่าง มิฉะนั้นใช้ RP/แผนเดิมต่อ (Week แรกไม่มีแผนที่ผ่าน บังคับ `hold` ทั้งสัปดาห์)
- **ไม่มี Stop Order, Liquidation และ Funding**:
  - **ไม่มี stop order (SL)** จำกัดความเสี่ยงด้วย `collateral` ของ Layer เพื่อถือ `position` ติดลบ (`NAV(-)`) รอแก้ได้
  - Layer ตาย (**liquidate** ปิดทั้ง Layer) เมื่อราคาแย่สุดระหว่าง Tick (`low` ฝั่ง `long`, `high` ฝั่ง `short`) ทำให้ `layer equity ≤ maintenance margin` (`collateral + unrealized PnL ≤ notional ÷ (2 × max_leverage)`; แท่งเดียวแตะทั้ง TP และ liquidation ให้ **liquidation ชนะ**) `collateral` เหลือ `0` และ Slot ว่าง
  - `liq price` ขึ้นกับ `collateral`, `entry`, `size`, `maintenance margin` เท่านั้น (unrealized PnL ไม่เปลี่ยน `liq price` แค่เปลี่ยนระยะห่างจากราคาตลาด) ตอน `open` หัก taker fee จาก `collateral` ครั้งเดียว ส่วน `funding` หัก/เพิ่มใน `collateral` ทุกชั่วโมงเต็ม (UTC) เมื่อ `collateral` ลดลงจาก fee และจ่าย funding จึงดัน **`liq price` เข้าใกล้ราคาปัจจุบันเมื่อเวลาผ่านไป** (ห่างออกเมื่อรับ funding)
- **Hostage (เชลย)**: ปิดด้วย `close` (taker fee) หรือแตะ `TP` (`high ≥ TP` ฝั่ง `long`, `low ≤ TP` ฝั่ง `short`, maker fee) คืน `collateral ± realized PnL − fee` เข้า `free_equity` และ Slot ว่าง กำไรใน `free_equity` เหนือ `collateral` ของ RP คือ **Hostage** ใช้: (1) ปิดชดเชย `NAV(-)` (basket offset), (2) สะสมจน `free_equity ≥ collateral` เปิด Slot ที่เคย liquidate, (3) รอรวมใน `equity` ตอน Reallocation

## 2. ชุด Action และ Hard Rule (Violation)

Action ประมวลผลตามลำดับ รายการที่ผิดกฎถูกปฏิเสธเป็น **Violation** (รายการอื่นทำงานต่อ) และแจ้งรหัสใน **Tick ถัดไป** คำสั่งนอกเหนือจาก 5 Action นี้ (หรือยังไม่เปิดใช้) ถูกปฏิเสธด้วย `unsupported_action`:

- `slot` นอกช่วง `0..3` ถูกปฏิเสธด้วย `slot_out_of_range`
- **`open(slot, symbol, side)`** (`"long"` | `"short"`, market fill ตาม RP) ถูกปฏิเสธเมื่อ:
  - `layer_occupied`: Slot ไม่ว่าง
  - `insufficient_free_equity`: `free_equity < collateral` ใน RP
  - `symbol_not_in_watchlist`: `symbol` ไม่อยู่ใน `watchlist` ของแผน
  - `bias_mismatch`: `bias` เป็น `avoid` หรือ `side` ไม่ตรง `bias` (`both` เปิดได้ทั้งคู่)
  - `opposite_side_open`: มี Layer อื่นถือ `symbol` เดียวกันทิศตรงข้าม (ซ้อนทิศเดียวกันคนละ Layer ได้)
  - `exceeds_max_leverage`: `notional ÷ collateral > max_leverage` ของ `symbol`
- **`close(slot)`** (market ปิดทั้ง Layer), **`set_tp(slot, price)`** (ตั้ง/แทนที่ limit TP), **`cancel_tp(slot)`** (ลบ TP):
  - `layer_empty`: Slot ว่าง
  - `tp_wrong_side`: `set_tp` ที่ `price` ไม่อยู่ฝั่งกำไรของ `entry` (`long`: `price > entry`, `short`: `price < entry`)
- **`hold`**: คงสถานะเดิม

## 3. Soft Rule (TSM Principle 4)

1. **Wait & See และ "หยุดให้เป็น"**: เปิด Layer เฉพาะเมื่อเข้าจุด **Action Based Strategy** (จุดเข้าตามแผน ไม่ใช่ทายทิศทาง) ไม่เข้าเงื่อนไขให้ `hold` เมื่อเก็บ Hostage ได้ตามจังหวะหรือใช้ Layer ครบตามแผนให้หยุดรอดู
2. **คุม EGO และทำตามแผน 100%**: ยึด RP คงที่ ไม่เปิดเกินแผนตอนชนะหรือรีบเอาคืนตอนแพ้ ทำตาม `entry`, `exit`, นโยบาย Hostage และเงื่อนไขปิดทุก Layer ในแผน
3. **Scenario A–E เมื่อถือ `NAV(-)` (unrealized PnL ติดลบ)**: ตราบที่ยังห่าง `liq price` เลือกทางแก้แทนตัดขาดทุนทันที — **(A)** หยุดเปิดเพิ่ม ถือ `NAV(-)` รอฟื้น **(B)** ถือ `NAV(-)` ไว้แล้วเปิด Layer ถัดไปใน Slot ว่าง **(C)** ถือ Layer บวกต่อสะสม Hostage **(D) Basket Offset** ปิด Layer บวกเก็บ Hostage มา `close` `NAV(-)` **(E)** ปิดเฉพาะ Layer บวกเก็บ Hostage แล้วถือ `NAV(-)` รอต่อ
4. **Zero Alpha & ขอบเขตกฎ**: ยึด **Zero Alpha** (เทรดตามราคาจริงปัจจุบัน / Reality & Flow ไม่ยึดติดความคาดหวัง) TSM Principle 4 ไม่มี entry criteria, timeframe, TP หรือ daily loss limit ทั้งหมดขึ้นกับ Tactic ในแผน
