# trading-bench

Benchmark ให้คู่โมเดล (Strategist + Executor) เทรด perp บน Hyperliquid ด้วยเงินจำลองตาม TSM Principle 4
spec อยู่ที่ `docs/spec/0001-trading-bench.md` คำศัพท์อยู่ใน `GLOSSARY.md` เหตุผลการออกแบบอยู่ใน `docs/adr/`

ใช้ Python 3 stdlib อย่างเดียว ไม่มี dependency

```sh
python3 -m unittest discover -s tests
```

## รันบน GitHub Actions

`.github/workflows/bench.yml` รันทุกชั่วโมงที่นาทีที่ 7 และกดรันเองได้จาก workflow_dispatch ทุก workflow run รัน `run-week` ก่อน `run-tick`
- ถ้า Week นี้มี Weekly Plan แล้ว `run-week` จะจบทันทีโดยไม่เรียก Hyperliquid หรือโมเดล และไม่เขียนอะไร
- จันทร์ 00:07 UTC ได้ Weekly Plan ใหม่ก่อน Tick ของชั่วโมงนั้น ถ้า GitHub ทิ้ง workflow run นั้นไป run ตอน 01:07 จะสร้างแทน
- ถ้า `run-week` ล้ม `run-tick` ยังรันต่อด้วย Weekly Plan ล่าสุด
- Hyperliquid ล้ม: Tick ถูกบันทึกว่า skipped ใน `data/runs.jsonl` และ workflow run ยังจบแบบสำเร็จ Tick ถัดไป settle ช่วงที่หายทั้งหมด

แต่ละ workflow run ทำสามอย่าง
- commit `data/` กับ `site/data/` กลับเข้า main
- deploy `site/` ขึ้น GitHub Pages
- อัปโหลด `artifacts/` เป็น artifact ของ run (เก็บ 90 วัน)

ใน artifact มีสองอย่าง
- prompt ดิบ (`prompts/`)
- คำตอบ Hyperliquid ที่ใช้ (`market/`) ซึ่งเป็นที่มาของ snapshot id ใน `responses.jsonl`

### ตั้งค่าครั้งแรก

```sh
gh repo create trading-bench --public --source . --push
gh secret set OPENROUTER_API_KEY            # วาง key เมื่อถูกถาม
gzip -9c ~/.trading-bench/tsm_full.md | base64 | gh secret set TSM_FULL_B64
gh api -X POST repos/{owner}/{repo}/pages -f build_type=workflow
```

`~/.trading-bench/tsm_full.md` คือสำเนา TSM Principle 4 เต็มฉบับจาก Obsidian
- เอกสารนี้ไม่ใช่ของเรา จึงเผยแพร่ใน repo public ไม่ได้ และ `.gitignore` กันไว้แล้ว
- workflow ถอด secret ลงไฟล์ใน `$RUNNER_TEMP` นอก working tree แล้วส่ง path ให้ Engine ผ่าน `TSM_FULL_PATH` ไฟล์นี้จึงไม่ถูก commit ไม่อยู่ใน artifact และไม่ถูก echo ลง log
- gzip -9 แล้ว base64 ได้ ~25KB ซึ่งต่ำกว่าเพดาน secret 48KB
- ถ้าแก้ไฟล์ต้นฉบับ ให้รันบรรทัด `TSM_FULL_B64` ซ้ำ

### เริ่ม Week 1

หลังตั้งค่าเสร็จ workflow run แรก (ตาม cron หรือกด Run workflow ใน Actions) จะสร้าง Weekly Plan ของ Week ปัจจุบันให้ทุก Contestant แล้ว Tick ต่อทันที

## รันด้วยมือ

`run-week` และ `run-tick` รับ `--data` (state), `--out` (dashboard export) และ `--artifacts` (prompt ดิบ) ส่วน `reset` รับแค่ `--data` และ `--out` ถ้าทดลอง ให้ชี้ไปที่โฟลเดอร์ชั่วคราว อย่าใช้ `data/` กับ `site/data/` จริง

### Fixture: ไม่เสียค่าโมเดล

ใช้ `--response` แทนคำตอบของโมเดลทุกตัวด้วย JSON ตายตัว ถ้าใช้คู่กับ `--fixtures` จะ replay คำตอบ Hyperliquid ที่ `--record` ไว้ จึงรันได้โดยไม่ต้องต่อเน็ต `run-week` ต้องมี `TSM_FULL_PATH` เสมอ ถ้าไม่มีไฟล์จริง ให้ใช้ไฟล์ปลอมใน tests

```sh
export TSM_FULL_PATH=tests/fixtures/fake_tsm_full.md
echo '{"notional": 2500, "watchlist": [{"symbol": "BTC", "bias": "both", "entry": "breakout", "exit": "TP +1%"}], "close_all": "Friday 20:00 UTC", "hostage_policy": "reopen lost Slots first", "rationale": "fixture"}' > /tmp/tb-plan.json
echo '{"reasoning": "fixture", "actions": [{"type": "hold"}]}' > /tmp/tb-hold.json
AT=$(date -u +%Y-%m-%dT%H:07:00Z)
# ครั้งแรก: Hyperliquid จริง (ฟรี ~1 นาที) บันทึกคำตอบไว้
python3 -m bench run-week --at $AT --response /tmp/tb-plan.json --record /tmp/tb/market --data /tmp/tb/data --out /tmp/tb/site
python3 -m bench run-tick --at $AT --response /tmp/tb-hold.json --record /tmp/tb/market --data /tmp/tb/data --out /tmp/tb/site
# replay ออฟไลน์ ได้ผลเหมือนเดิมทุก byte
python3 -m bench run-week --at $AT --response /tmp/tb-plan.json --fixtures /tmp/tb/market --data /tmp/tb/data2 --out /tmp/tb/site2
python3 -m bench run-tick --at $AT --response /tmp/tb-hold.json --fixtures /tmp/tb/market --data /tmp/tb/data2 --out /tmp/tb/site2
```

ถ้าอยากดู dashboard ตัวอย่างที่ครอบคลุมทุกกรณี:

```sh
python3 -m tests.sample_site && python3 -m http.server 8777 -d .sample
```

### Live: มีค่าใช้จ่าย OpenRouter

```sh
export OPENROUTER_API_KEY=... TSM_FULL_PATH=~/.trading-bench/tsm_full.md
AT=$(date -u +%Y-%m-%dT%H:07:00Z)
python3 -m bench run-week --at $AT --data /tmp/tb/data --out /tmp/tb/site --artifacts /tmp/tb/prompts --record /tmp/tb/market
python3 -m bench run-tick --at $AT --data /tmp/tb/data --out /tmp/tb/site --artifacts /tmp/tb/prompts --record /tmp/tb/market
```

## Reset

ปิด workflow ก่อน ไม่อย่างนั้น workflow run ที่กำลังรันอยู่จะ `git pull --rebase` แล้วชนกับ commit ที่ลบ `data/`

```sh
gh workflow disable bench.yml       # แล้วรอให้ workflow run ที่ค้างอยู่จบ
python3 -m bench reset              # ลบ data/ และ site/data/
git add -A data site/data && git commit -m "reset" && git push
gh workflow enable bench.yml        # workflow run ถัดไปเริ่ม Week 1 ใหม่
```

## เพิ่ม Contestant

เพิ่ม `{"name", "strategist", "executor"}` (model id ของ OpenRouter) ใน `config.json` แล้ว push
Contestant ใหม่จะเริ่มที่ `run-week` ของ workflow run ถัดไป คือภายในหนึ่งชั่วโมง และได้ Weekly Plan ของ Week ที่กำลังดำเนินอยู่
