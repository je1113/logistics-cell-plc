# 물류 분류 셀: PLC · 로봇 · HMI 연동 시뮬레이션

컨베이어 · PLC · 로봇 · HMI가 신호를 주고받으며 하나의 피킹 작업을 완성하는 물류 분류 셀을 시뮬레이션으로 구현한 프로젝트입니다.

로봇 소프트웨어를 공부하며 "로봇이 실제 현장에서 주변 설비와 어떻게 맞물려 동작하는가"를 이해하기 위해 시작했습니다. 래더로 제어 로직을 설계하고, Modbus TCP로 PLC와 로봇의 핸드셰이크를 구현한 뒤, C# HMI와 자동 테스트, 측정까지 진행했습니다.

| 항목 | 내용 |
|---|---|
| 래더 설계 · 검증 | XG5000, XG-SIM (LS ELECTRIC XGB) |
| 가상 PLC · 로봇 | Python, pymodbus |
| HMI | C# WinForms (.NET 8), NModbus |
| 통신 | Modbus TCP |
| 결과 | 정상 사이클 ○○/20회 · 평균 사이클 타임 ○.○○ s · 로봇 무응답 알람 ○/5회 감지 |

## 구성

```
 [작업자]
    │ 버튼 · 램프
 [HMI (C# WinForms)]
    │ Modbus TCP (Coil 0~7)
 [가상 PLC (Python)] ──── 래더 로직 설계 · 검증: XG5000 / XG-SIM
    │ Modbus TCP (Coil 0~4)
 [로봇 클라이언트 (Python)]
```

## 폴더 구조

```
ladder/       XG5000 프로젝트 파일과 래더 캡처 (자기유지 · 정지 지연 · 인터록 · 비상정지)
plc_sim/      가상 PLC 서버와 핸드셰이크 자동 테스트
robot_sim/    로봇 클라이언트 (피킹 동작은 2초 대기로 대체)
hmi/CellHmi/  C# WinForms HMI
measure/      사이클 타임 · 성공률 · 알람 감지 시간 측정 스크립트와 결과
docs/         신호 명세서
```

## 핵심 설계

**1. 신호는 켜는 것만큼 끄는 시점이 중요하다**
요청 → 수락 → 동작 중 → 완료 → 요청 해제 → 응답 초기화까지를 하나의 약속으로 정의했습니다. 이전 사이클의 완료 신호가 남아 다음 사이클을 잘못 시작하지 않습니다. → [신호 명세서](docs/signal_spec.md)

**2. 응답이 없으면 기다리지 않고 멈춘다**
요청 수락 3초, 작업 완료 10초 타임아웃을 두고, 넘으면 알람을 켜고 셀 정상 신호를 끕니다. 알람 중 들어온 요청은 무시하고 리셋 후에만 다시 시작합니다.

**3. HMI는 요청만 하고, 처리 기록은 PLC가 남긴다**
HMI 버튼 신호는 PLC가 읽은 뒤 스스로 끕니다. 통신이 끊기면 HMI는 마지막 상태 대신 램프를 모두 끄고 "통신 끊김"을 표시합니다.

## 실행 방법

```bash
pip install -r requirements.txt

# 터미널 1: 가상 PLC (엔터 = 박스 도착)
python plc_sim/plc_server.py

# 터미널 2: 로봇
python robot_sim/robot_client.py

# HMI: Visual Studio에서 hmi/CellHmi/CellHmi.csproj를 열고 실행 → [연결]
```

## 테스트

신호 약속이 지켜지는지 가상 PLC와 로봇을 실제로 띄워 확인합니다.

```bash
pytest plc_sim/test_handshake.py -v
```

| 테스트 | 확인하는 것 |
|---|---|
| `test_initial_state` | 시작 직후 셀 정상만 ON |
| `test_normal_cycle` | 요청 → 수락 → 완료 → 요청 해제 → 초기화 순서 |
| `test_box_signal_is_cleared_by_plc` | HMI 버튼 신호를 PLC가 처리 후 OFF |
| `test_ack_timeout_raises_alarm` | 로봇 무응답 시 3초 뒤 알람, 요청·셀 정상 OFF |
| `test_box_ignored_during_alarm` | 알람 중 박스 도착 무시 |
| `test_reset_then_normal_cycle` | 리셋 후 정상 사이클 복귀 |

## 측정 결과

```bash
python measure/measure.py cycle 20     # 가상 PLC · 로봇 실행 상태
python measure/measure.py timeout 5    # 로봇 종료 상태
```

| 항목 | 결과 |
|---|---|
| 성공률 | ○○ / 20회 |
| 사이클 타임 | 평균 ○.○○○ s · 최소 ○.○○○ s · 최대 ○.○○○ s |
| 요청 → 수락 | 평균 ○○ ms · 최대 ○○ ms |
| 알람 감지 | ○ / 5회 · 평균 ○.○○○ s (설정 3.0 s) |

로봇 동작은 실제 모션 대신 2초로 고정한 가상 시간입니다. 사이클 타임은 로봇 성능이 아니라 신호 처리와 핸드셰이크에 걸리는 시간을 보여줍니다. 원본 데이터는 `measure/results/`에 있습니다.

## 한계와 다음 단계

| 아직 검증하지 못한 것 | 확인 방법 |
|---|---|
| 실제 LS PLC의 Modbus 주소 매핑 | 실물 XGB PLC와 통신 모듈로 P/M 영역 대응 확인 |
| XG-SIM 래더와 외부 통신 연결 | 실물 PLC에 래더를 다운로드해 가상 PLC 자리를 대체 |
| 실제 로봇 동작 | 로봇 클라이언트의 2초 대기를 실제 피킹 동작으로 교체 |
| PLC 측 통신 끊김 감지 | 하트비트 신호를 두고 일정 시간 변화가 없으면 정지 |

비상정지는 안전 회로(안전 릴레이, Safety PLC)에서 처리해야 하므로, 래더에서는 비상 상태 유지와 재기동 방지 로직만 연습했습니다.

## 블로그 시리즈: 로봇 개발자의 PLC 공부

| 회차 | 주제 |
|---|---|
| #0 | [로봇이 움직이는 것만으로는 부족했다](<링크>) |
| #1 | [PLC는 어떻게 일하는가](<링크>) |
| #2 | [XG5000 설치하고 첫 프로젝트 만들기](https://dingirl.tistory.com/229) |
| #3 | [자기유지 회로](https://dingirl.tistory.com/230) |
| #4 | [타이머와 센서: 박스가 오면 멈춘다](https://dingirl.tistory.com/231) |
| #5 | [인터록과 비상정지](<링크>) |
| #6 | [PLC와 로봇은 어떻게 대화할까: 신호 설계와 Modbus TCP](https://dingirl.tistory.com/233) |
| #7 | [C#으로 HMI 만들기](<링크>) |
| #8 | [물류 분류 셀 완성: 하나로 묶고 숫자로 확인하기](<링크>) |
