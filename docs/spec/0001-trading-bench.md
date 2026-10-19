---
status: draft
date: 2026-10-18
glossary: ../../GLOSSARY.md
adrs: [0001-layer-liquidation-is-the-stop-loss, 0002-github-actions-with-retroactive-settlement, 0003-market-data-given-to-models]
---

# Trading Bench: AI perp paper-trading benchmark บน Hyperliquid ภายใต้ TSM Principle 4

## Problem Statement

ไม่มีทางรู้ว่า AI model แต่ละค่าย "เทรดเป็น" แค่ไหนเมื่อถูกบังคับให้อยู่ในกรอบบริหารทรัพยากรเดียวกัน Benchmark ที่มีอยู่วัดความรู้หรือการเขียนโค้ด ไม่ได้วัดการตัดสินใจภายใต้ความไม่แน่นอน ต้นทุนจริง (fee, funding) และการต้องทำตามแผนที่ตัวเองหรือตัวใหญ่กว่าวางไว้ ผู้ใช้อยากเห็นว่า เมื่อให้โมเดลใหญ่วางกลยุทธ์รายสัปดาห์ และโมเดลเล็กของค่ายเดียวกันลงมือรายชั่วโมง โดยทุกคู่ถูกบังคับด้วยกฎ TSM Hostage Hunt ชุดเดียวกัน ค่ายไหนทำเงินได้มากกว่ากัน และพลาดตรงไหน

## Solution

ระบบ paper trading ที่จำลองตลาด perp ของ Hyperliquid จากข้อมูลจริง (ราคา, L2, funding, max leverage) ให้ Contestant 6 คู่ (Strategist + Executor ค่ายเดียวกัน) แข่งกัน 12 สัปดาห์ด้วย Paper Account 10,000 USDC ต่อคู่ Engine บังคับ Hard Rule ของ TSM (4 Layer collateral เท่ากัน position notional คงที่ ไม่มี stop ปิดกองเมื่อ liquidate) ปล่อยให้ Strategist คิด "Tactic" เอง ทุกการตัดสินใจและ reasoning ถูกบันทึกและแสดงบน dashboard สาธารณะที่อัปเดตทุกชั่วโมง จัดอันดับด้วย Net Return

## User Stories

### ผู้ดู benchmark

1. As a ผู้ดู benchmark, I want a leaderboard จัดอันดับ Contestant ด้วย Net Return, so that เห็นทันทีว่าค่ายไหนนำ
2. As a ผู้ดู benchmark, I want equity curve ของทุก Contestant ซ้อนกันในกราฟเดียว, so that เปรียบเทียบเส้นทางไม่ใช่แค่ปลายทาง
3. As a ผู้ดู benchmark, I want ตัวชี้วัดรอง (Max Drawdown, จำนวน position ที่ปิด, win rate, PnL เฉลี่ยต่อ Layer, จำนวน Layer ที่ถูก liquidate, จำนวน Violation, fee และ funding สะสม), so that แยกได้ว่าชนะเพราะโชคหรือเพราะวินัย
4. As a ผู้ดู benchmark, I want หน้าของแต่ละ Contestant ที่แสดง Layer ที่เปิดอยู่ (สินค้า ทิศ notional entry mark PnL liq price TP), so that รู้ว่าตอนนี้ถืออะไร
5. As a ผู้ดู benchmark, I want ประวัติทุก position ที่ปิดแล้ว (เวลาเปิด/ปิด ราคา fee funding PnL เหตุผลที่ปิด: Executor สั่ง / TP / liquidation), so that ตรวจย้อนหลังได้ทุกไม้
6. As a ผู้ดู benchmark, I want อ่าน Weekly Plan ทุกสัปดาห์พร้อม rationale ของ Strategist, so that เข้าใจว่าคิดอะไรก่อนลงมือ
7. As a ผู้ดู benchmark, I want อ่าน reasoning ของ Executor ทุก Tick คู่กับ Action ที่สั่ง, so that เห็นว่าทำตามแผนหรือแถ
8. As a ผู้ดู benchmark, I want รายการ Violation พร้อม Action ที่ถูกปฏิเสธและกฎที่ขัด, so that รู้ว่าโมเดลไหนไม่เข้าใจกฎ
9. As a ผู้ดู benchmark, I want เห็น Contestant ที่ถูก Elimination ถูกทำเครื่องหมายชัดพร้อมสัปดาห์ที่ตกรอบ, so that ไม่สับสนว่าทำไมเส้นหยุด
10. As a ผู้ดู benchmark, I want เห็นเวลาที่ Tick ล่าสุดเกิดและสถานะว่ารอบนี้สำเร็จหรือข้าม, so that รู้ว่าข้อมูลสดแค่ไหน
11. As a ผู้ดู benchmark, I want เปิด dashboard บนมือถือได้, so that ตามผลระหว่างวัน

### Strategist (โมเดลตัวหลัก)

12. As a Strategist, I want ได้รับ TSM Principle 4 เต็มฉบับ, so that วางแผนในกรอบที่ถูกบังคับ
13. As a Strategist, I want ได้รับแผนและผลเทรดทุกไม้ของสัปดาห์ก่อน พร้อม reasoning ของ Executor, so that วิเคราะห์ว่าแผนถูกทำตามไหมและผิดตรงไหน
14. As a Strategist, I want ได้รับภาพตลาดกว้าง (daily/weekly candles ของ top 50 perp ตาม volume, funding, OI, max leverage), so that เลือก watchlist ได้
15. As a Strategist, I want ระบุสินค้านอก top 50 ได้ถ้ามันมีบน Hyperliquid, so that ไม่ถูกจำกัดโดย universe ที่ส่งมา
16. As a Strategist, I want กำหนด notional ต่อ Layer เองใน RP, so that เลือกความดุของกลยุทธ์
17. As a Strategist, I want เขียนเงื่อนไข entry/exit และเงื่อนไข "ปิดทุกกอง" เป็นข้อความอิสระ, so that Tactic เป็นของตัวเอง
18. As a Strategist, I want ได้รับ error ที่ชัดเจนและโอกาสแก้แผนเมื่อ Engine ปฏิเสธ, so that ไม่เสียสัปดาห์เพราะ format
19. As a Strategist, I want รู้สถานะปัจจุบันตอนวางแผน (equity, free equity, Layer ที่ค้าง, RP ปัจจุบัน และว่า Reallocation จะเกิดหรือไม่), so that แผนสอดคล้องกับความจริง

### Executor (โมเดลตัวเล็ก)

20. As an Executor, I want ได้รับ Weekly Plan และสรุปกฎ TSM แบบย่อฉบับเดียวกันทุก Tick, so that ตัดสินใจในกรอบ
21. As an Executor, I want เห็นข้อมูลตลาดเฉพาะสินค้าใน watchlist หลาย timeframe พร้อม funding, OI, mark, so that วิเคราะห์ได้โดย prompt ไม่บวม
22. As an Executor, I want เห็นสถานะบัญชีและ Layer ปัจจุบัน รวมถึง liq price ของแต่ละกอง, so that รู้ว่ากองไหนใกล้ตาย
23. As an Executor, I want เห็น event ที่ Engine settle ไปในชั่วโมงที่ผ่านมา (TP fill, liquidation), so that ไม่สั่งปิดกองที่ไม่มีแล้ว
24. As an Executor, I want เห็น log การเทรดและ reasoning ของตัวเองในสัปดาห์นี้, so that ไม่ลืมว่าเปิดเพราะอะไร
25. As an Executor, I want ชุด Action เล็กและชัด (open, close, set_tp, cancel_tp, hold), so that ตอบเป็น JSON ได้ถูกเสมอ
26. As an Executor, I want รู้เหตุผลเมื่อ Action ถูกปฏิเสธ (ใน Tick ถัดไป), so that ไม่ทำผิดซ้ำ

### ผู้ดูแลระบบ

27. As a ผู้ดูแล, I want เพิ่ม/ลด Contestant ด้วย config เดียว, so that ลองค่ายใหม่ได้โดยไม่แก้โค้ด
28. As a ผู้ดูแล, I want ค่าธรรมเนียม ทุนเริ่มต้น เกณฑ์ Elimination จำนวนสัปดาห์ และ universe size อยู่ใน config, so that ปรับได้โดยไม่แตะ logic
29. As a ผู้ดูแล, I want ระบบรันบน GitHub Actions ฟรี ไม่มี server, so that ไม่มีค่าใช้จ่ายโครงสร้างและไม่มีอะไรให้ดูแล
30. As a ผู้ดูแล, I want state ทั้งหมดอยู่ใน repo เป็นไฟล์อ่านได้, so that ตรวจ ย้อน และกู้คืนได้ด้วย git
31. As a ผู้ดูแล, I want response ของโมเดลทุกครั้งถูกเก็บถาวร และ prompt ดิบเก็บเป็น workflow artifact, so that debug การตัดสินใจแปลกๆ ได้
32. As a ผู้ดูแล, I want ทุก Tick บันทึก snapshot id ของข้อมูลตลาดที่ใช้, so that ประกอบ prompt ซ้ำได้
33. As a ผู้ดูแล, I want ให้ Tick ที่พลาด (cron ดีเลย์, API ล่ม) ถูกชดเชยด้วยการ settle ย้อนหลัง, so that ความถูกต้องของบัญชีไม่ขึ้นกับความตรงเวลา
34. As a ผู้ดูแล, I want รัน Tick หรือ Week ด้วยมือกับข้อมูลที่บันทึกไว้, so that ทดสอบ Engine โดยไม่เรียก API จริง
35. As a ผู้ดูแล, I want เริ่ม benchmark ใหม่ (reset state) ด้วยคำสั่งเดียว, so that เริ่มรอบใหม่ได้สะอาด

## Implementation Decisions

### ผู้เล่นและทุน

- Contestant 6 คู่ เรียกผ่าน OpenRouter ทั้งหมด จับคู่ตามค่าย: Anthropic (claude-fable-5.1 / claude-haiku-5.5), OpenAI (gpt-6-astra / gpt-6-luna), Google (gemini-4-argon / gemini-3.8-flash), Qwen (qwen3.8-max-prime / qwen3.8-flash), Z.ai (glm-5.3-prime / glm-5.3-flash), DeepSeek (deepseek-v4-pro-0813 / deepseek-v4.1-flash) รายชื่ออยู่ใน config ไม่ hardcode
- ทุกโมเดลใช้ temperature default ของค่าย ไม่มี tool ไม่มี web search บังคับตอบเป็น JSON ตาม schema
- Paper Account เริ่ม 10,000 USDC แยกขาดต่อ Contestant ไม่เติมทุน Elimination เมื่อ equity < 1,000 USDC แล้วหยุดเรียกโมเดลของคู่นั้นถาวร ใช้ equity นั้นเป็นคะแนน
- ระยะเวลา 12 Week เป็น forward test สด Week เริ่มจันทร์ 00:00 UTC

### จังหวะเวลา (ตาม ADR-0002)

- Weekly workflow รันจันทร์ 00:07 UTC: ต่อ Contestant ทำตามลำดับ settle ชั่วโมงที่ค้าง → ประเมิน Reallocation → เรียก Strategist → validate แผน → บันทึก
- Hourly workflow รันนาทีที่ 7 ของทุกชั่วโมง: ต่อ Contestant ทำตามลำดับ settle ย้อนหลัง → ประกอบ prompt → เรียก Executor → validate และ apply Action → บันทึก → export dashboard data → commit
- ทั้งสอง workflow ใช้ concurrency group เดียวกัน รันซ้อนไม่ได้ Tick ที่พลาดไม่ถูกย้อนกลับไปตัดสินใจ แต่ Tick ถัดไป settle ช่วงที่หายทั้งหมด
- Tick แรกของ Week จะเกิดหลัง Weekly Plan ถูกบันทึกแล้วเท่านั้น ถ้า weekly workflow ยังไม่เสร็จหรือล้ม Executor ใช้แผนล่าสุดที่มี

### โมเดลตลาดจำลอง

- แหล่งข้อมูล: Hyperliquid public info API อย่างเดียว (meta + asset contexts สำหรับ mark, funding, OI, max leverage; L2 book สำหรับ fill; candle snapshot สำหรับ 1m/15m/1H/4H/1D/1W; funding history สำหรับการ settle ย้อนหลัง)
- Open: market order fill ที่ best ask (long) / best bid (short) จาก L2 snapshot ณ เวลา Tick ไม่คิด slippage เพิ่ม คิด taker fee
- Close โดย Executor: market order fill แบบเดียวกัน คิด taker fee
- TP: reduce-only limit หนึ่งรายการต่อ Layer ถือว่า fill เต็มจำนวนที่ราคา TP เมื่อแท่ง 1m ใด high ≥ TP (long) หรือ low ≤ TP (short) คิด maker fee ตั้ง TP ใหม่แทนที่ของเดิม
- Funding: ทุกชั่วโมงเต็ม (UTC) ใช้ funding rate จริงของชั่วโมงนั้นจาก funding history คิดจาก notional ปัจจุบัน หัก/เพิ่มเข้า collateral ของ Layer ที่ถือ position
- Liquidation (ตาม ADR-0001): Layer ถูกปิดทั้งกองที่ราคา mark ของแท่ง 1m ที่ทำให้ layer equity ≤ maintenance margin โดย maintenance = notional / (2 × max leverage ของสินค้า) ใช้ high/low ของแท่ง 1m เป็น proxy ของ mark ที่เลวร้ายสุด collateral ที่เหลือหลัง liquidation = 0 (ไม่คืน)
- การ settle ย้อนหลังไล่ตามเวลาแท่ง 1m: ในแท่งเดียวกันถ้าทั้ง TP และ liquidation เข้าเงื่อนไข ให้ liquidation ชนะ (อนุรักษ์นิยม) ทุก event บันทึก timestamp ของแท่งไม่ใช่เวลา Tick
- Fee: taker 0.045%, maker 0.015% (Hyperliquid base tier) เป็นค่า config

### โมเดล Layer (ตาม ADR-0001)

- มี 4 Layer เสมอ Layer คือบัญชีย่อยที่ถือ collateral คงที่และ position ได้หนึ่งตัว
- RP = { collateral ต่อ Layer, notional ต่อ position } collateral ถูกกำหนดเป็น equity ÷ 4 ณ Reallocation notional มาจาก Weekly Plan ทั้งสองค่าเท่ากันทุก Layer และคงที่จนกว่าจะ Reallocation ครั้งถัดไป
- Reallocation เกิดเฉพาะที่ขอบ Week และเฉพาะเมื่อไม่มี Layer ใดถือ position ถ้ามีกองค้าง RP เดิมใช้ต่อทั้งสัปดาห์ และ notional ในแผนใหม่ถูกบันทึกว่า "ไม่ถูกใช้" (ไม่ใช่ Violation) Week แรกทุก Layer ว่างเสมอจึง Reallocation แน่
- Open Layer ได้เมื่อมี Slot ว่าง และ free equity ≥ collateral Engine ล็อก collateral เต็มจำนวนเข้า Layer ตอนเปิด จากนั้น fee และ funding ของ position หักจาก collateral นั้น
- Close Layer (โดย Executor, TP หรือ liquidation) ปล่อย collateral ± PnL สุทธิกลับ free equity Slot ว่าง ส่วนที่เกินทุนเดิมใน free equity คือ Hostage ซึ่งใช้เปิด Slot ที่เสียไปใหม่ได้เมื่อสะสมถึง collateral
- Equity ของ Contestant = free equity + Σ (collateral + unrealized PnL ของทุก Layer ที่เปิด) นี่คือค่าที่ใช้ทั้ง Net Return และ Elimination
- ห้ามถือ long และ short สินค้าเดียวกันพร้อมกันในบัญชีเดียว (คนละ Layer ก็ไม่ได้) ซ้อนสินค้าเดียวทิศเดียวในหลาย Layer ได้

### Weekly Plan

- โครงสร้าง: notional ต่อ Layer เป็น USD, watchlist สูงสุด 5 รายการ แต่ละรายการมี symbol, bias (long / short / both / avoid), เงื่อนไข entry เป็นข้อความ, เงื่อนไข exit เป็นข้อความ; เงื่อนไข "ปิดทุกกอง" เป็นข้อความ (เพื่อให้ Reallocation สัปดาห์หน้าเกิด); นโยบายใช้ Hostage เป็นข้อความ; rationale เป็นข้อความยาว
- Validation ตอนรับแผน: symbol ทุกตัวมีบน Hyperliquid, watchlist ≤ 5, notional ≥ ขั้นต่ำของ Hyperliquid (10 USD), notional ÷ collateral ที่จะใช้จริง ≤ max leverage ของทุก symbol ใน watchlist (collateral ที่ใช้คือค่าใหม่ถ้าจะ Reallocation ไม่เช่นนั้นค่าเดิม)
- ไม่ผ่าน → ส่ง error กลับให้ Strategist retry ได้ 2 ครั้ง ยังไม่ผ่าน → ใช้แผนสัปดาห์ก่อนทั้งฉบับ Week แรกถ้าไม่ผ่าน → Contestant นั้นไม่มีแผน Executor ถูกบังคับ hold ทั้งสัปดาห์ และบันทึก Violation หนึ่งรายการ
- Executor เทรดได้เฉพาะ symbol ใน watchlist ที่ bias ไม่ใช่ avoid และทิศต้องตรง bias (both = ได้ทั้งคู่)

### Executor

- Input ต่อ Tick: สรุปกฎ TSM แบบย่อ (ไฟล์เดียวใน repo ใช้ร่วมทุก Contestant), Weekly Plan ปัจจุบัน, สถานะบัญชี (equity, free equity, RP, ทุก Layer พร้อม entry/mark/unrealized/liq price/TP), event ที่ settle ไปตั้งแต่ Tick ก่อน, Action ที่ถูกปฏิเสธใน Tick ก่อนพร้อมเหตุผล, log การเทรดและ reasoning ของตัวเองในสัปดาห์นี้, ข้อมูลตลาดต่อ symbol ใน watchlist: candle 4H × 30, 1H × 24, 15m × 16 แต่ละ series มี Indicator Pack กำกับ, %change 24h/7d, daily VWAP (anchor 00:00 UTC), mark, funding rate ปัจจุบันและคาดการณ์, OI, max leverage
- Output: reasoning เป็นข้อความ + รายการ Action โดย Action มี 5 ชนิด: open (slot, symbol, side), close (slot), set_tp (slot, price), cancel_tp (slot), hold ไม่มี limit entry ไม่มี stop ไม่มี partial ไม่มีระบุขนาด
- Engine apply Action ตามลำดับที่ส่งมา รายการที่ขัด Hard Rule หรือ Weekly Plan ถูกปฏิเสธเป็นรายรายการ (รายการอื่นยัง apply) และบันทึกเป็น Violation พร้อมกฎที่ขัด
- Hard Rule ที่ Engine ตรวจ: Slot ว่างและ free equity พอ, symbol อยู่ใน watchlist และทิศตรง bias, ไม่เกิด long+short สินค้าเดียวกัน, notional ÷ collateral ≤ max leverage ของ symbol, TP อยู่ฝั่งกำไรของ entry, slot ที่อ้างมีอยู่จริง
- Soft Rule (Wait & See, คุม EGO, basket offset, Scenario Analysis) อยู่ในสรุปย่อให้โมเดลอ่าน Engine ไม่ตรวจ

### Indicator Pack (ตาม ADR-0003)

- Engine คำนวณด้วย stdlib จากแท่งที่ดึงมา ~200 แท่งต่อ timeframe แล้วส่งเฉพาะส่วนท้ายของ candle ตามจำนวนข้างต้น pack เหมือนกันทุก Contestant และมี `indicator_pack_version` บันทึกคู่กับทุก response ห้ามเปลี่ยนนิยามหลัง Week 1 เริ่ม
- ต่อ series (ทุก timeframe ที่ส่ง ยกเว้น weekly) คำนวณจากแท่งที่ปิดแล้วเท่านั้น ค่าแบบ series ส่ง 3 จุด: ปัจจุบัน, 1 แท่งก่อน, 5 แท่งก่อน: EMA 20, EMA 50 (seed ด้วย SMA); RSI 14 (Wilder; ราคานิ่งตลอด = 50); ATR 14 (Wilder) ทั้งเป็นราคาและ % ของ close; MACD 12/26/9 (line, signal, histogram) ส่วน swing เป็นจุดเดียวต่อฝั่ง: swing high และ swing low ล่าสุดที่ยืนยันแล้วแบบ fractal 3 แท่งซ้าย/ขวา (ราคา, จำนวนแท่งที่ผ่านมา) บวก `swing_position` ค่าเดียว (close ล่าสุดอยู่เหนือ swing high / ใต้ swing low / ระหว่าง และเป็น null เมื่อขาด swing ด้านใดด้านหนึ่ง)
- ต่อ symbol: %change ของ close เทียบ 24h และ 7d ก่อน (Strategist เพิ่ม 30d); VWAP จากแท่ง 15m ด้วย typical price (H+L+C)/3 × volume พร้อม % ระยะห่างของราคาจาก VWAP และจำนวนแท่งที่สะสมแล้ว โดย Executor ได้ daily VWAP anchor ที่ 00:00 UTC ของวันนั้น (หลังเที่ยงคืนใหม่ๆ เป็น null + 0 แท่ง) ส่วน Strategist ได้ VWAP ของสัปดาห์ที่เพิ่งจบ ช่วง [จันทร์ก่อนหน้า 00:00, จันทร์นี้ 00:00) เพราะ run-week เกิดไม่กี่นาทีหลังขอบ Week ซึ่งสัปดาห์ใหม่ยังไม่มีแท่งปิด
- ทดสอบเป็น pure function (series → ค่า) ด้วย fixture คงที่เทียบค่าอ้างอิง เป็น seam ที่สองนอกเหนือจาก Tick เฉพาะคณิตล้วน ส่วน Tick seam ตรวจแค่ว่า pack ถูกแนบครบทุก symbol/timeframe

### Strategist

- Input ต่อ Week: TSM Principle 4 เต็มฉบับ, Weekly Plan สัปดาห์ก่อน, ทุก position ที่เปิด/ปิดในสัปดาห์ก่อนพร้อม reasoning ของ Executor ตอนเปิดและปิด, Violation ของสัปดาห์ก่อน, สถานะบัญชีปัจจุบันและว่าจะเกิด Reallocation หรือไม่ (พร้อม collateral ที่จะได้), universe = top 50 perp ตาม 24h volume พร้อม daily candle × 30 พร้อม Indicator Pack, weekly candle × 26 ดิบ, %change 24h/7d/30d, VWAP ของสัปดาห์ที่เพิ่งจบ, funding เฉลี่ย 7 วัน, OI, max leverage; รายชื่อ symbol ทั้งหมดบน Hyperliquid (ชื่ออย่างเดียว) เพื่อให้เลือกนอก top 50 ได้
- Output: Weekly Plan ตามโครงสร้างด้านบน

### ความล้มเหลว

- เรียกโมเดลล้มเหลวหรือตอบไม่ตรง schema: retry 1 ครั้ง ยังล้ม → Tick นั้นถือว่า hold บันทึก error ไม่นับ Violation
- Hyperliquid API ล่ม: ข้าม Tick ทั้งรอบสำหรับทุก Contestant (เท่าเทียม) Tick ถัดไป settle ช่วงที่หาย
- ข้อมูล 1m ย้อนหลังที่ดึงได้มีขีดจำกัด ถ้าช่วงที่หายยาวกว่าที่ดึงได้ ให้ settle ด้วย 15m แล้ว 1H ตามลำดับ และบันทึกว่าใช้ความละเอียดใด

### การเก็บข้อมูลและ dashboard

- State ทั้งหมดเป็นไฟล์ JSON ใน repo แยกต่อ Contestant: บัญชี/Layer ปัจจุบัน, event log แบบ append-only (fill, funding, liquidation, TP, violation, error), Weekly Plan ทุกสัปดาห์, response ของโมเดลทุกครั้ง, equity snapshot ทุก Tick
- Prompt ดิบของทุกการเรียกเก็บเป็น workflow artifact (90 วัน) และทุกการเรียกบันทึก snapshot id ของข้อมูลตลาดที่ใช้
- Dashboard เป็น static site บน GitHub Pages อ่าน JSON จาก repo ตรง ไม่มี backend แสดงหน้าตาม user story 1–11 ข้อมูลที่ dashboard อ่านถูก export เป็นไฟล์สรุปแยกจาก state ภายในเพื่อไม่ผูกหน้าเว็บกับโครงสร้าง Engine
- Repo เป็น public ดังนั้น TSM Principle 4 เต็มฉบับ (เนื้อหาของผู้เขียน TSM ไม่ใช่ของโปรเจกต์) ไม่ถูก commit: รันจริงอ่านจาก GitHub Secret ที่ถอดเป็นไฟล์ชั่วคราว รัน local อ่านจาก path ใน env var ส่วนสรุปย่อสำหรับ Executor ที่เราเขียนเองอยู่ใน repo ได้

### ตัวชี้วัด

- หลัก: Net Return = (equity ปัจจุบัน − 10,000) ÷ 10,000 รวม unrealized หัก fee และ funding
- รอง (แสดง ไม่ถ่วงอันดับ): Max Drawdown จาก equity snapshot รายชั่วโมง, จำนวน position ปิด, win rate, PnL เฉลี่ยต่อ position, จำนวน liquidation, Violation รวม, fee รวม, funding สุทธิรวม, จำนวนสัปดาห์ที่ Reallocation เกิด

## Testing Decisions

- ทดสอบพฤติกรรมภายนอกของ Engine เท่านั้น: ให้ข้อมูลตลาดที่บันทึกไว้ + response โมเดลที่เขียนสคริปต์ไว้ → รัน Tick/Week → ตรวจสถานะบัญชี, event log และ Violation ที่ออกมา ไม่ทดสอบ prompt wording หรือ parser ย่อย
- **Seam เดียว**: "รัน Tick (หรือ Week) หนึ่งรอบ ณ เวลาที่กำหนด ด้วย market source และ model client ที่ฉีดเข้าไปได้" การรันจริงฉีด Hyperliquid API + OpenRouter การทดสอบฉีด fixture จากไฟล์และ response ที่กำหนดล่วงหน้า Seam นี้ตรงกับ user story 34 (รันด้วยมือกับข้อมูลที่บันทึก) จึงไม่ใช่ seam ที่สร้างเพื่อทดสอบอย่างเดียว
- สถานการณ์ที่ต้องมี test อย่างน้อยหนึ่งชุด: open แล้วถูกคิด taker fee และล็อก collateral; funding หักจาก collateral ของกองที่ถือ; TP fill จากแท่ง 1m กลางชั่วโมงด้วย maker fee และ timestamp ของแท่ง; liquidation เมื่อ layer equity ≤ maintenance รวมกรณี funding ดันให้ถึง; TP กับ liquidation ในแท่งเดียวกัน liquidation ชนะ; Hostage สะสมแล้วเปิด Slot ที่เสียไปใหม่ได้; Reallocation เกิดเฉพาะเมื่อทุกกองว่างที่ขอบ Week; แผนไม่ผ่าน validation → retry → fallback; Action ที่ขัดกฎถูกปฏิเสธรายรายการโดยรายการอื่นยัง apply; ห้าม long+short สินค้าเดียว; Elimination หยุดการเรียกโมเดล; Tick ที่หายหลายชั่วโมงถูก settle ครบ; โมเดลตอบพังถือเป็น hold
- ไม่มี prior art ใน repo (โปรเจกต์ใหม่) ใช้ unittest จาก stdlib ไม่เพิ่ม framework
- Dashboard ไม่มี automated test ตรวจด้วยตาจาก JSON ตัวอย่างที่ test ของ Engine ผลิตออกมา

## Out of Scope

- Buffer / "Step 2" ของ TSM (เอากำไรไปเทรดเสี่ยงด้วย RP คนละชุด) รอ version 2
- การจับคู่ไขว้ Strategist กับ Executor ต่างค่าย
- Limit entry, stop order, partial close, การเพิ่ม/ลดขนาด position, การแบ่งย่อยภายใน Layer
- การวางแผนใหม่กลางสัปดาห์
- ข่าว โซเชียล on-chain หรือข้อมูลนอก Hyperliquid; L2 order book สำหรับโมเดล; indicator นอกรายการใน Indicator Pack (รวม indicator อิง volume อื่นนอกจาก VWAP)
- Replay / backtest ย้อนหลังด้วยความเร็วสูง (รองรับแค่รันด้วยมือกับ fixture)
- Slippage นอกเหนือจาก L2 snapshot, fee tier อื่นนอกจาก base, referral discount
- ระบบ auth, การสั่งงานผ่าน dashboard, backend ใดๆ
- xAI และค่ายอื่นที่ไม่มีคู่ แพง+ถูก ชัดเจน (เพิ่มได้ภายหลังผ่าน config)

## Further Notes

- TSM Principle 4 ไม่มี entry criteria, timeframe, TP หรือ daily loss limit การที่ Strategist ต้องคิด Tactic เองคือสิ่งที่ benchmark วัด ไม่ใช่ช่องโหว่
- การ map "SL" เป็น liquidation และไม่มี stop order เป็นการเลือกของผู้ใช้โดยรู้ว่า Contestant อาจเสียทั้งบัญชีในสัปดาห์เดียว (ADR-0001)
- สรุปกฎ TSM ฉบับย่อสำหรับ Executor เป็นไฟล์ที่มนุษย์เขียนและ review ได้ เป็นส่วนเดียวของ prompt ที่ "ตีความ" เอกสาร จึงควรตรึง version และบันทึก hash ไว้กับทุก response
- ค่าใช้จ่ายโมเดลประเมินไว้ไม่เกินสิบดอลลาร์ต่อสัปดาห์สำหรับ 6 Contestant ตัวแพงสุดคือ Gemini flash ฝั่ง Executor
- ศัพท์ทั้งหมดอ้างตาม GLOSSARY.md ที่ root ของ repo
