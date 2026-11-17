"""가상 로봇 (Modbus TCP 클라이언트)
피킹 요청을 읽으면 수락 → 동작 중 → (2초) → 완료, 요청이 꺼지면 신호를 모두 초기화한다.
"""
import time
from pymodbus.client import ModbusTcpClient

REQ, READY, ACK, BUSY, DONE = 0, 1, 2, 3, 4
PICK_SECONDS = 2.0

def log(msg): print(f"[ROBOT {time.strftime('%H:%M:%S')}] {msg}", flush=True)

def main():
    client = ModbusTcpClient("127.0.0.1", port=5020)
    if not client.connect():
        log("PLC 서버에 연결할 수 없음"); return
    log("PLC 연결됨, 피킹 요청 대기")
    try:
        while True:
            rr = client.read_coils(0, count=2)
            if rr.isError():
                log("읽기 실패 → 로봇 정지"); break
            req, ready = rr.bits[0], rr.bits[1]
            if req and ready:
                log("피킹 요청 수신 → 요청 수락 ON")
                client.write_coil(ACK, True)
                client.write_coil(BUSY, True);  log("동작 중 ON (피킹 수행)")
                time.sleep(PICK_SECONDS)
                client.write_coil(BUSY, False)
                client.write_coil(DONE, True);  log("피킹 완료 ON")
                while client.read_coils(REQ, count=1).bits[0]:   # PLC가 요청을 끌 때까지
                    time.sleep(0.05)
                client.write_coils(ACK, [False, False, False]); log("요청 OFF 확인 → 수락·동작중·완료 초기화")
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()

if __name__ == "__main__":
    main()
