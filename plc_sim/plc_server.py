"""가상 PLC (Modbus TCP 서버)
Coil 0 피킹 요청 (PLC→로봇)   Coil 1 셀 정상 (PLC→로봇)
Coil 2 요청 수락 (로봇→PLC)   Coil 3 동작 중 (로봇→PLC)   Coil 4 피킹 완료 (로봇→PLC)
Coil 5 박스 도착 (HMI→PLC)    Coil 6 알람 리셋 (HMI→PLC)   Coil 7 알람 (PLC→HMI)
엔터를 누르거나 HMI에서 Coil 5를 켜면 박스가 도착한 것으로 보고 피킹 요청을 켠다.
"""
import asyncio, time
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.server import StartAsyncTcpServer

REQ, READY, ACK, BUSY, DONE, BOX, RESET, ALARM = 0, 1, 2, 3, 4, 5, 6, 7
ACK_TIMEOUT = 3.0     # 요청 후 수락까지
DONE_TIMEOUT = 10.0   # 수락 후 완료까지

block = ModbusSequentialDataBlock(0, [False] * 10)
context = ModbusServerContext(slaves=ModbusSlaveContext(co=block), single=True)

def get(a): return context[0].getValues(1, a, 1)[0]
def put(a, v): context[0].setValues(1, a, [v])

def log(msg): print(f"[PLC {time.strftime('%H:%M:%S')}] {msg}", flush=True)

async def plc_logic(box_event):
    put(READY, True)
    state, t0 = "IDLE", time.monotonic()
    while True:
        await asyncio.sleep(0.05)                     # 스캔 주기 50ms
        ack, busy, done = get(ACK), get(BUSY), get(DONE)
        if get(BOX):                                  # HMI 버튼은 한 번 읽고 바로 끈다
            put(BOX, False); box_event.set()
        if get(RESET):
            put(RESET, False)
            if state == "ALARM":
                put(ALARM, False); put(READY, True); state = "IDLE"; log("알람 리셋 → 셀 정상 ON")
        if state == "IDLE" and box_event.is_set():
            box_event.clear(); put(REQ, True); state, t0 = "WAIT_ACK", time.monotonic()
            log("박스 도착 → 피킹 요청 ON")
        elif state == "WAIT_ACK":
            if ack: state, t0 = "WAIT_DONE", time.monotonic(); log("요청 수락 확인")
            elif time.monotonic() - t0 > ACK_TIMEOUT:
                put(REQ, False); put(READY, False); put(ALARM, True); state = "ALARM"
                log("알람: 요청 수락 타임아웃 → 셀 정상 OFF")
        elif state == "WAIT_DONE":
            if done:
                put(REQ, False); state = "WAIT_CLEAR"; log("피킹 완료 확인 → 피킹 요청 OFF")
            elif time.monotonic() - t0 > DONE_TIMEOUT:
                put(REQ, False); put(READY, False); put(ALARM, True); state = "ALARM"
                log("알람: 작업 완료 타임아웃 → 셀 정상 OFF")
        elif state == "ALARM" and box_event.is_set():
            box_event.clear(); log("알람 중이라 박스 도착 무시 (리셋 필요)")
        elif state == "WAIT_CLEAR" and not (ack or busy or done):
            state = "IDLE"; log("로봇 신호 초기화 확인 → 컨베이어 재가동 허용")

async def keyboard(box_event):
    loop = asyncio.get_running_loop()
    while True:
        await loop.run_in_executor(None, input)
        box_event.set()

async def main():
    box_event = asyncio.Event()
    log("Modbus TCP 서버 시작 (127.0.0.1:5020) · 엔터 = 박스 도착")
    await asyncio.gather(
        StartAsyncTcpServer(context=context, address=("127.0.0.1", 5020)),
        plc_logic(box_event), keyboard(box_event))

if __name__ == "__main__":
    asyncio.run(main())
