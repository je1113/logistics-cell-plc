"""물류 분류 셀 측정 스크립트 (HMI 역할로 접속해 측정)
사용법
  python measure.py cycle 20   # 정상 사이클 20회: 사이클 타임·성공률 (plc_server, robot_client 실행 상태)
  python measure.py timeout 5  # 로봇 무응답 5회: 알람까지 걸린 시간 (robot_client 종료 상태)
결과는 화면 요약 + CSV 파일로 저장한다.
"""
import csv, statistics, sys, time
from pymodbus.client import ModbusTcpClient

REQ, READY, ACK, BUSY, DONE, BOX, RESET, ALARM = 0, 1, 2, 3, 4, 5, 6, 7
POLL = 0.01            # 10ms마다 확인
CYCLE_LIMIT = 15.0     # 이 시간 안에 끝나지 않으면 실패로 본다

def coils(c):
    return c.read_coils(0, count=8).bits[:8]

def wait_until(c, cond, limit):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limit:
        b = coils(c)
        if cond(b):
            return time.perf_counter(), b
        time.sleep(POLL)
    return None, coils(c)

def run_cycles(c, n):
    rows = []
    for i in range(1, n + 1):
        if not coils(c)[READY]:
            c.write_coil(RESET, True); time.sleep(0.2)
        t0 = time.perf_counter()
        c.write_coil(BOX, True)
        t_req, _ = wait_until(c, lambda b: b[REQ], CYCLE_LIMIT)
        t_ack, _ = wait_until(c, lambda b: b[ACK], CYCLE_LIMIT) if t_req else (None, None)
        t_done, _ = wait_until(c, lambda b: b[DONE], CYCLE_LIMIT) if t_ack else (None, None)
        t_end, b = (wait_until(c, lambda b: not (b[REQ] or b[ACK] or b[BUSY] or b[DONE]), CYCLE_LIMIT)
                    if t_done else (None, coils(c)))
        ok = t_end is not None and not b[ALARM]
        row = {
            "cycle": i, "success": ok,
            "req_ms": round((t_req - t0) * 1000) if t_req else "",
            "ack_ms": round((t_ack - t_req) * 1000) if t_ack else "",
            "cycle_s": round(t_end - t0, 3) if ok else "",
        }
        rows.append(row)
        print(f"{i:>3}회 {'성공' if ok else '실패'}  사이클 {row['cycle_s']} s  요청→수락 {row['ack_ms']} ms", flush=True)
        time.sleep(0.2)
    times = [r["cycle_s"] for r in rows if r["success"]]
    acks = [r["ack_ms"] for r in rows if r["success"]]
    print(f"\n성공률 {len(times)}/{n}")
    if times:
        print(f"사이클 타임 평균 {statistics.mean(times):.3f} s · 최소 {min(times):.3f} s · 최대 {max(times):.3f} s")
        print(f"요청→수락 평균 {statistics.mean(acks):.0f} ms · 최대 {max(acks)} ms")
    return rows, "cycle_result.csv"

def run_timeouts(c, n):
    rows = []
    for i in range(1, n + 1):
        c.write_coil(RESET, True); time.sleep(0.2)
        c.write_coil(BOX, True)
        t_req, _ = wait_until(c, lambda b: b[REQ], 5)
        t_alarm, b = wait_until(c, lambda b: b[ALARM], 10) if t_req else (None, None)
        ok = t_alarm is not None and not b[REQ] and not b[READY]
        row = {"trial": i, "alarm_ok": ok, "alarm_s": round(t_alarm - t_req, 3) if t_alarm else ""}
        rows.append(row)
        print(f"{i:>3}회 알람 {'감지' if ok else '실패'}  요청→알람 {row['alarm_s']} s", flush=True)
    c.write_coil(RESET, True)
    vals = [r["alarm_s"] for r in rows if r["alarm_ok"]]
    print(f"\n알람 감지 {len(vals)}/{n}")
    if vals:
        print(f"요청→알람 평균 {statistics.mean(vals):.3f} s (설정 3.0 s) · 최대 {max(vals):.3f} s")
    return rows, "timeout_result.csv"

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "cycle"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else (20 if mode == "cycle" else 5)
    c = ModbusTcpClient("127.0.0.1", port=5020)
    if not c.connect():
        print("PLC 서버에 연결할 수 없음"); return
    rows, path = run_cycles(c, n) if mode == "cycle" else run_timeouts(c, n)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    print(f"저장: {path}")
    c.close()

if __name__ == "__main__":
    main()
