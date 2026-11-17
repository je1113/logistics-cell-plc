"""핸드셰이크 자동 테스트
가상 PLC 서버와 로봇 클라이언트를 실제로 띄우고, HMI 역할로 Coil을 읽고 쓰며 신호 약속을 확인한다.
실행: pytest plc_sim/test_handshake.py -v
"""
import subprocess, sys, time
from pathlib import Path

import pytest
from pymodbus.client import ModbusTcpClient

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "plc_sim" / "plc_server.py"
ROBOT = ROOT / "robot_sim" / "robot_client.py"

REQ, READY, ACK, BUSY, DONE, BOX, RESET, ALARM = 0, 1, 2, 3, 4, 5, 6, 7
ACK_TIMEOUT = 3.0


def start(script):
    # plc_server는 엔터 입력을 기다리므로 stdin을 열어 둔다
    return subprocess.Popen([sys.executable, str(script)], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop(proc):
    proc.terminate()
    proc.wait(timeout=5)


def coils(c):
    return c.read_coils(0, count=8).bits[:8]


def wait_until(c, cond, limit):
    """조건이 참이 될 때까지 기다리고 걸린 시간을 돌려준다. 시간 안에 안 되면 None."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limit:
        if cond(coils(c)):
            return time.perf_counter() - t0
        time.sleep(0.01)
    return None


@pytest.fixture
def plc():
    server = start(SERVER)
    client = ModbusTcpClient("127.0.0.1", port=5020)
    for _ in range(50):                       # 서버가 뜰 때까지 최대 5초
        if client.connect():
            break
        time.sleep(0.1)
    else:
        stop(server)
        pytest.fail("가상 PLC 서버에 연결할 수 없음")
    yield client
    client.close()
    stop(server)


@pytest.fixture
def robot(plc):
    proc = start(ROBOT)
    time.sleep(0.5)
    yield proc
    if proc.poll() is None:
        stop(proc)


def test_initial_state(plc):
    """시작 직후에는 셀 정상만 ON이고 나머지는 모두 OFF다."""
    assert wait_until(plc, lambda b: b[READY], 2) is not None
    b = coils(plc)
    assert not any([b[REQ], b[ACK], b[BUSY], b[DONE], b[ALARM]])


def test_normal_cycle(plc, robot):
    """요청 → 수락 → 완료 → 요청 해제 → 응답 초기화 순서로 한 사이클을 마친다."""
    plc.write_coil(BOX, True)
    assert wait_until(plc, lambda b: b[REQ], 2) is not None, "피킹 요청이 켜지지 않음"
    assert wait_until(plc, lambda b: b[ACK], 2) is not None, "로봇이 수락하지 않음"
    assert wait_until(plc, lambda b: b[DONE], 5) is not None, "피킹 완료가 오지 않음"
    assert wait_until(plc, lambda b: not b[REQ], 2) is not None, "PLC가 요청을 끄지 않음"
    assert wait_until(plc, lambda b: not (b[ACK] or b[BUSY] or b[DONE]), 2) is not None, "로봇 신호가 초기화되지 않음"
    b = coils(plc)
    assert b[READY] and not b[ALARM]


def test_box_signal_is_cleared_by_plc(plc):
    """HMI가 켠 박스 도착 신호는 PLC가 읽은 뒤 스스로 끈다."""
    plc.write_coil(BOX, True)
    assert wait_until(plc, lambda b: not b[BOX], 1) is not None


def test_ack_timeout_raises_alarm(plc):
    """로봇이 응답하지 않으면 설정 시간(3초) 뒤 알람을 켜고 셀 정상과 요청을 끈다."""
    plc.write_coil(BOX, True)
    assert wait_until(plc, lambda b: b[REQ], 2) is not None
    elapsed = wait_until(plc, lambda b: b[ALARM], ACK_TIMEOUT + 2)
    assert elapsed is not None, "알람이 켜지지 않음"
    assert ACK_TIMEOUT - 0.2 <= elapsed <= ACK_TIMEOUT + 0.5
    b = coils(plc)
    assert not b[REQ] and not b[READY]


def test_box_ignored_during_alarm(plc):
    """알람 중에 들어온 박스 도착은 무시한다."""
    plc.write_coil(BOX, True)
    assert wait_until(plc, lambda b: b[ALARM], ACK_TIMEOUT + 2) is not None
    plc.write_coil(BOX, True)
    time.sleep(0.5)
    b = coils(plc)
    assert not b[REQ] and b[ALARM]


def test_reset_then_normal_cycle(plc):
    """알람을 리셋하면 셀 정상이 돌아오고, 이후 정상 사이클이 다시 동작한다."""
    plc.write_coil(BOX, True)
    assert wait_until(plc, lambda b: b[ALARM], ACK_TIMEOUT + 2) is not None
    plc.write_coil(RESET, True)
    assert wait_until(plc, lambda b: b[READY] and not b[ALARM], 1) is not None
    robot = start(ROBOT)
    try:
        time.sleep(0.5)
        plc.write_coil(BOX, True)
        assert wait_until(plc, lambda b: b[DONE], 5) is not None
        assert wait_until(plc, lambda b: not (b[REQ] or b[ACK] or b[BUSY] or b[DONE]), 2) is not None
    finally:
        stop(robot)
