# SpotMicro Week 13 — 외부 원격 조종: 공유기 없이 폰 핫스팟으로

> 작성일: 2026-09-15

---

## 1. 문제 — 리모트 컨트롤이 집 공유기에 묶여 있었다

`Common/web_control.py` 웹 UI로 폰에서 조종하는 방식인데, rpi와 폰이 같은
공유기(`mesh5168`)에 붙어 있어야만 동작했다. 로봇을 들고 밖에 나가면
공유기가 없으니 조종이 안 됐다.

## 2. 검토한 방법

- **Tailscale 등 오버레이 VPN**: 인터넷만 있으면 어디서든 붙지만, NAT 환경에서
  릴레이(DERP)를 타면 지연이 늘어난다. 실시간 조종에는 부적합하다고 판단해 제외.
- **rpi를 자체 AP로 띄우기(hostapd)**: 딜레이가 제일 낮고 구조도 단순하지만,
  폰이 조종하는 동안 다른 인터넷을 못 쓴다.
- **폰 개인 핫스팟에 rpi를 클라이언트로 붙이기**: 로컬 wifi라 딜레이는 AP
  방식과 비슷하고, 폰은 모바일 데이터로 인터넷도 계속 쓸 수 있다.

세 번째(폰 핫스팟)로 결정했다.

## 3. 구현 — netplan에 핫스팟을 두 번째 access-point로 등록

rpi(RPi-CM4, Ubuntu 24.04, systemd-networkd + netplan)의
`/etc/netplan/50-cloud-init.yaml`에는 이미 집 AP `mesh5168`이 PSK로 등록돼
있었다. 여기에 폰 핫스팟(`iPhone-Yirugo`)을 access-point 하나 더 추가했다.

```yaml
wifis:
  wlan0:
    access-points:
      "mesh5168": {...}
      "iPhone-Yirugo": {...}
```

우선순위 필드는 따로 없고, wpa_supplicant가 스캔 시 신호 세기(RSSI)가 제일
센 쪽으로 붙는다 — 집에서는 `mesh5168`, 밖에서 핫스팟을 켜면 그쪽으로 자동
전환된다.

## 4. 함정 — SSID 철자가 한 글자만 달라도 조용히 실패한다

netplan의 `password` 필드는 평문이 아니라
`PBKDF2-SHA1(password, ssid, 4096, 32byte)`로 미리 해시한 PSK다. SSID 문자열
자체가 해시의 솔트라서, 처음에 SSID를 `iPhone-Yirugo`(공백 없음)로 넣었는데
실제 아이폰이 내보내는 이름은 `iPhone - Yirugo`(하이픈 앞뒤에 공백)였다.
비밀번호는 맞았지만 SSID가 달라 그 네트워크엔 아예 접속되지 않았고, 에러
메시지도 없이 조용히 실패했다.

하필 이 상태에서 테스트용으로 `mesh5168` 항목을 주석 처리해둔 채
`netplan apply`를 해버려서, rpi가 두 wifi 어느 쪽에도 못 붙는 상태가 됐다.
`eth0`에 걸어둔 고정 IP(`192.168.88.20/24`)로 직결 복구를 시도했으나 로봇이
이미 조립된 상태라 케이블을 꽂을 수 없었다. 결국 반대로 접근해서 아이폰
기기 이름(설정 > 일반 > 정보 > 이름)을 rpi에 이미 들어있던 철자
`iPhone-Yirugo`에 맞춰 바꾸는 것으로 재접속시켰다.

## 5. 정리

| 값 | 정본 |
|---|---|
| SSID | 기기가 실제로 내보내는 문자열 그대로 (`nmcli dev wifi` 등으로 확인 후 그대로 복사) |
| PSK | `wpa_passphrase <ssid> <password>` 결과. SSID가 바뀌면 반드시 재계산 |

핫스팟 SSID를 다시 바꿀 일이 있으면 netplan의 PSK도 같이 재계산해야 한다.

이제 `mesh5168`과 `iPhone-Yirugo` 둘 다 등록돼 있어 집/외부 전환이
자동으로 된다. 웹 컨트롤 서버(`RaspberryPi/start_automatic_gait.py`)는
자동 시작되지 않으므로, 조종 전에 rpi에 ssh로 들어가서 수동으로 띄워야
한다.
