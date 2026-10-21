# 07: เรียกโมเดลจริงผ่าน OpenRouter และประกอบ prompt

**What to build:** model client ตัวจริงที่เรียก OpenRouter ด้วย model id จาก config, บังคับ JSON output ตาม schema ของ Executor (reasoning + Action list) และ Strategist (Weekly Plan), temperature default ของค่าย ไม่มี tool; client **ไม่ retry เอง**: หน้าที่มีแค่เรียก OpenRouter แล้ว parse JSON และ raise exception ใดก็ได้เมื่อล้ม เพราะ Engine (ticket 04) เป็นคน retry และ validate schema อยู่แล้ว โดยส่ง error ของครั้งก่อนมาใน key `retry_error` ของ request ซึ่ง prompt ต้องแสดงให้โมเดลเห็น ประกอบ prompt ของ Executor ตาม spec (สรุปกฎ TSM ฉบับย่อจาก ticket 02 พร้อม hash, Weekly Plan, สถานะบัญชี/Layer/liq price, event ที่ settle, Violation ก่อนหน้า, log สัปดาห์นี้, candle 4H × 30 / 1H × 24 / 15m × 16 ต่อ symbol พร้อม Indicator Pack จาก ticket 10, %change, daily VWAP, mark, funding, OI, max leverage) และของ Strategist (รวม TSM เต็มฉบับ) ทุกการเรียกบันทึก response ดิบ + snapshot id ของข้อมูลตลาด + hash ของสรุป TSM ลง repo และเขียน prompt ดิบลงโฟลเดอร์ artifact ให้ workflow อัปโหลด

**Blocked by:** 02 (สรุปกฎ TSM ฉบับย่อ), 04 (Hard Rule ครบชุด), 05 (Weekly Plan และ Reallocation), 10 (Indicator Pack)

**Status:** ready-for-agent

- [x] รัน `run-tick` จริงกับ Contestant เดียวด้วย OpenRouter key แล้วได้ Action ที่ parse ผ่านและ apply ได้ (ทดสอบด้วยมือหนึ่งครั้งต่อค่ายทั้ง 6 คู่ บันทึกผลใน ticket)
- [x] client ล้ม (network, timeout, JSON พัง) → raise ออกมาให้ Engine จัดการ ไม่ retry เอง ไม่กลืน exception
- [x] เมื่อ request มี `retry_error` prompt แสดง error นั้นให้โมเดลเห็นก่อนตอบใหม่ (ตรวจด้วย test ว่า prompt ที่ประกอบมีข้อความ error)
- [x] prompt ของ Executor สำหรับ watchlist 5 ตัวมีขนาดไม่เกิน ~30k token และไม่มีข้อมูลสินค้านอก watchlist
- [x] ทุก response บันทึก `indicator_pack_version` คู่กับ hash ของสรุป TSM
- [x] prompt ของ Strategist มี TSM เต็มฉบับ, แผนและทุกไม้สัปดาห์ก่อนพร้อม reasoning, และข้อมูล universe ตาม spec
- [x] TSM เต็มฉบับ**ไม่อยู่ใน repo** (เป็นเนื้อหาของผู้อื่น repo เป็น public): Engine อ่านจาก path ใน env var `TSM_FULL_PATH` ถ้าไม่ตั้งหรือไฟล์ไม่มี → run-week ล้มด้วย error ที่บอกชื่อ env var ไม่ใช่ fallback เงียบ; path นั้นและชื่อไฟล์ที่น่าจะใช้อยู่ใน `.gitignore`; ทุก response ของ Strategist บันทึก sha256 ของไฟล์ที่อ่านได้จริง
- [x] test ประกอบ prompt ของ Strategist ใช้ไฟล์ TSM ปลอมสั้นๆ ใน fixture ไม่ใช่ไฟล์จริง
- [x] ทุก response เก็บถาวรพร้อม model id, snapshot id, hash สรุป TSM, token usage และ latency
- [x] prompt ดิบถูกเขียนลงโฟลเดอร์ artifact ที่ไม่ถูก commit
- [x] test: model client จำลอง HTTP ล้ม/ตอบพัง ผ่าน seam เดียว ไม่เรียก network
- [x] (จากผลรันจริง) ไม่ส่ง `provider.require_parameters` คง `response_format: json_schema` ไว้ เพราะ endpoint ของ z-ai/glm-5.3-prime ไม่รองรับ structured_outputs; system prompt ของ Strategist ระบุกติกา validation (watchlist ≤ 5 ไม่ซ้ำ อยู่ใน `symbols`, notional ≥ 10 USD, notional ÷ collateral ≤ max leverage ทุก symbol); `full_tsm()` จับ OSError ทุกชนิดแล้ว raise ข้อความที่บอกชื่อ env var
- [x] (ADR-0003 แก้แล้ว) weekly candle 12 แท่ง และ candle ทุก series ส่งแบบบีบ: timestamp เริ่มต้นครั้งเดียว + `[o, h, l, c, v]` ต่อแท่ง ราคาปัดตาม tick size จาก meta volume จำนวนเต็ม; `prompt_encoding_version` บันทึกคู่กับทุก response; float ทุกตัวที่ส่ง (pack, %change, VWAP, funding, volume) ปัด 5 significant figures ตอน encode เท่านั้น; test วัดว่า universe 50 symbol มีขนาดไม่เกิน 130k chars
- [x] รัน run-week จริงซ้ำหลังแก้ (data โฟลเดอร์ใหม่) ให้ครบ 6 ค่ายรวม zai แล้วรัน run-tick 1 ครั้งเพื่อพิสูจน์ Executor ทั้ง 6 ตัว บันทึกผลใน ticket
  - รอบสอง 2026-10-20: Strategist 5/6 ผ่านรอบแรกไม่ต้อง retry, prompt ลดเหลือ 81k–118k token (universe compact 125.9k chars); zai ตอบ JSON ผิดชนิด (close_all เป็น boolean, entry/exit เป็นตัวเลข) เพราะ provider ไม่บังคับ schema แล้วรอบ retry เจอ HTTP 402 Payment Required; Executor ทุกตัวได้ HTTP 403 → credit/limit ของ key หมด ต้องเติมแล้วรัน run-tick ใหม่
  - Tick 02:07 หลังเติม credit: Executor 5/5 ที่มีแผนตอบตรง schema ครั้งเดียว ไม่มี Violation: haiku hold (14.4k in / 0.8k out / 7s), luna hold (10.7k / 0.5k / 6s), gemini-3.8-flash hold (19.3k / 1.2k / 12s), qwen3.8-flash hold (11.6k / 3.6k / 103s), deepseek-v4.1-flash เปิด SOL short notional 10 + set_tp ฝั่งถูก (12.9k / 17.8k out / 161s); zai ไม่มีแผน → hold โดยไม่เรียกโมเดล ตามกติกา Executor prompt ทั้งหมดต่ำกว่า 20k token ข้อสังเกต: deepseek/qwen ตอบช้า 100–160s เพราะ reasoning ยาว ต้องเผื่อเวลา job ใน ticket 09 (Tick หนึ่งรอบอาจเกิน 10 นาที); Executor ของ zai ยังไม่ได้พิสูจน์จนกว่า Strategist ของ zai จะได้แผนที่ผ่าน
  - รอบสาม 2026-10-21 (`/tmp/tb-live3`, run-week 2026-10-19T00:07Z แล้ว run-tick 01:07Z) หลังเพิ่มชนิด field ใน prompt และเก็บ body ของ HTTP error: ทั้ง 6 ค่ายผ่าน ไม่มี Violation

    | ค่าย | role | ผล | in / out token | latency | หมายเหตุ |
    |---|---|---|---|---|---|
    | anthropic | Strategist fable-5.1 | ผ่าน | 107.9k / 3.9k | 61s | notional 2500, watchlist 4 |
    | anthropic | Executor haiku-5.5 | ผ่าน | 15.3k / 0.7k | 6s | `actions: []` |
    | openai | Strategist gpt-6-astra | ผ่าน | 81.8k / 1.4k | 32s | notional 2500, watchlist 4 |
    | openai | Executor gpt-6-luna | ผ่าน | 10.8k / 0.6k | 8s | hold |
    | google | Strategist gemini-4-argon | ผ่าน | 118.4k / 1.1k | 22s | notional 5000, watchlist 5 |
    | google | Executor gemini-3.8-flash | ผ่าน | 20.5k / 1.6k | 12s | hold |
    | qwen | Strategist qwen3.8-max-prime | ผ่าน | 115.4k / 3.3k | 49s | notional 10000, **watchlist ว่าง** |
    | qwen | Executor qwen3.8-flash | ผ่าน | 1.7k / 1.7k | 31s | hold (prompt เล็กเพราะ watchlist ว่าง จึงไม่มีข้อมูลตลาด) |
    | zai | Strategist glm-5.3-prime | ล้ม 1 ครั้ง แล้วผ่านตอน retry | 110.3k / 21.0k, 110.3k / 13.3k | 206s, 135s | ครั้งแรก: `each watchlist item needs symbol, bias (long/short/both/avoid), entry and exit (strings)` เพราะ `bias` เป็นข้อความบรรยาย (เช่น "Neutral-to-long inside the 79,730-84,300 range…") แทน enum; ชนิด field อื่นถูกหมดแล้ว; retry ได้ notional 10000, watchlist 5 |
    | zai | Executor glm-5.3-flash | ผ่าน | 16.2k / 0.5k | 4s | hold |
    | deepseek | Strategist deepseek-v4-pro-0813 | ผ่าน | 80.8k / 0.7k | 11s | notional 2500, watchlist 5 (short ล้วน) |
    | deepseek | Executor deepseek-v4.1-flash | ผ่าน | 13.1k / 1.4k | 7s | hold |
- [x] (จากรอบสอง) client เก็บ body ของ HTTP error (OpenRouter ส่ง JSON `error.message` เช่น insufficient credits / key limit / moderation) ลง error ใน archive ไม่ใช่แค่ "HTTP Error 403: Forbidden"; และ system prompt ของ Strategist ระบุชนิด field ให้ชัด (close_all, entry, exit เป็นข้อความ) เพื่อค่ายที่ provider ไม่บังคับ json_schema
- [x] (จากรอบสาม) watchlist ว่างถูกกติกา (spec แก้แล้ว): เมื่อแผนไม่มี watchlist และไม่มี Layer เปิด Engine บันทึก decision hold โดยไม่เรียก Executor (ประหยัด call ทั้งสัปดาห์); ถ้ามี Layer ค้างยังเรียกตามปกติ test ทั้งสองกรณีผ่าน Tick seam
