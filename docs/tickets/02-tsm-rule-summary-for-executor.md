# 02: เขียนสรุปกฎ TSM ฉบับย่อสำหรับ Executor

**What to build:** ไฟล์ข้อความหนึ่งไฟล์ (ภาษาไทย อังกฤษปนได้ ไม่เกิน ~2,000 token) ที่ Executor ทุกค่ายได้รับทุก Tick แทน TSM Principle 4 เต็มฉบับ แยกชัดเป็น Hard Rule (สิ่งที่ Engine ปฏิเสธ) และ Soft Rule (Wait & See, คุม EGO, basket offset, Scenario Analysis, "หยุดให้เป็น") พร้อมอธิบายกลไก Layer/Slot/Hostage/Reallocation/liquidation ตามที่ Engine ทำจริง ไฟล์นี้คือส่วนเดียวของ prompt ที่ "ตีความ" เอกสารต้นฉบับ จึงต้องมี version และถูก hash ไว้กับทุก response ในภายหลัง

**Blocked by:** None (can start immediately)

**Status:** done

- [x] อ้างอิงเฉพาะสิ่งที่อยู่ในเอกสาร TSM Principle 4 หรือใน spec ไม่เพิ่มกฎใหม่ (ไม่มี TP บังคับ ไม่มี timeframe ไม่มี daily loss limit)
- [x] ระบุชุด Action ทั้ง 5 และเงื่อนไขที่แต่ละอันจะถูกปฏิเสธ ตรงกับ Hard Rule ใน spec ทุกข้อ
- [x] อธิบายว่าไม่มี stop order และ Layer ตายเมื่อ collateral หมด พร้อมผลของ funding ต่อ liq price
- [x] มีบรรทัด version ที่ด้านบนไฟล์
- [x] ผู้ใช้ review แล้วยอมรับว่าตีความเอกสารถูก
