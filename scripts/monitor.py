"""等待两个 pipeline 产出文件后退出"""
import os
import sys
import time

temp_dir = sys.argv[1]
whisper_json = os.path.join(temp_dir, "transcript.json")
ocr_json = os.path.join(temp_dir, "subtitles_ocr.json")

print(f"[monitor] waiting for:")
print(f"  1. {whisper_json}")
print(f"  2. {ocr_json}")

start = time.time()
while True:
    w_ok = os.path.exists(whisper_json)
    o_ok = os.path.exists(ocr_json)
    elapsed = time.time() - start

    if w_ok and o_ok:
        print(f"[monitor] BOTH DONE! ({elapsed:.0f}s)")
        wsize = os.path.getsize(whisper_json)
        osize = os.path.getsize(ocr_json)
        print(f"  whisper: {wsize} bytes")
        print(f"  ocr:     {osize} bytes")
        break

    # 每 60 秒打印一次状态
    if int(elapsed) % 60 == 0 and int(elapsed) > 0:
        status = []
        status.append("whisper: DONE" if w_ok else "whisper: running")
        status.append("ocr: DONE" if o_ok else "ocr: running")
        print(f"[monitor] {elapsed:.0f}s elapsed | {' | '.join(status)}")

    time.sleep(5)

print("[monitor] exiting.")
