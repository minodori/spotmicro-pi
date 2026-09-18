# Tailscale 서브넷 라우터 - DSM 한 대로 내부망 전체 열기

> 작성일: 2026-09-18

집 안의 기기마다 Tailscale 을 설치하고 각각 관리하던 것을, **NAS 한 대만 서브넷
라우터로 두고 나머지는 내부 IP 로 접근**하는 구성으로 바꿨다.

---

## 0. 결론부터

외부에서 Tailscale 만 켜면 집 안 기기에 **내부 IP 그대로** 접근한다.

```
외부 노트북/폰 (Tailscale)
   |
DSM 192.168.0.172  (서브넷 라우터, 192.168.0.0/24 광고)
   |
ender-5 .7 / ender-3v3 .8 / RPi-CM4 .9 / desktop-minho .16 / desktop-server .3
```

| 대상 | 이전 | 이제 |
|---|---|---|
| SBC | 각 기기에 Tailscale 설치 후 100.x 주소 | `ssh minodori@192.168.0.7` |
| desktop-minho | `219.248.24.178:5170` (포트포워딩) | `192.168.0.16:3389` |
| desktop-server | `219.248.24.178:5171` (포트포워딩) | `192.168.0.3:3389` |

RDP 포트포워딩을 없앨 수 있다. RDP 를 인터넷에 직접 노출하지 않는 것이 이 구성의
가장 큰 보안 이득이다.

**Tailscale 이 필요한 쪽은 접속하는 기기뿐이다.** 집 안 기기는 설치하지 않는다.

접속하는 장소도 `192.168.0.x` 를 쓰면 대역이 겹쳐 로컬이 먼저 잡힌다. 이때는
[4via6](#6-대역이-겹칠-때---4via6) 이름으로 접속한다.

```bash
ssh minodori@ender-5-v6
```

---

## 1. 왜 이렇게 바꿨나

기기마다 설치하면 각각 업데이트하고 각각 인증을 갱신해야 한다. 기기가 늘수록
관리 지점이 늘어난다. 서브넷 라우터는 관리 지점이 하나다.

> 무료 플랜의 기기 수 제한 때문이라고 생각했는데, 확인해 보니 현재 Personal 플랜은
> **사용자 6명, 기기 무제한**이다. 제한은 이유가 아니었고 관리 편의가 이유다.

---

## 2. 설정 절차

### 2.1 DSM 에서 경로 광고

```bash
tailscale up --advertise-routes=192.168.0.0/24
```

Synology 에서는 `--accept-routes` 를 쓸 수 없다. 붙이면 **명령 전체가 실패**하고
설정이 하나도 적용되지 않는다.

```
--accept-routes is not supported on Synology; see tailscale/tailscale#1995
```

DSM 이 다른 노드의 경로를 받을 일은 없으므로 빼면 된다.

### 2.2 관리 콘솔에서 승인

https://login.tailscale.com/admin/machines 에서 `dsm` -> `...` -> **Edit route settings**
-> `192.168.0.0/24` 체크 -> Save.

광고만으로는 열리지 않는다. 승인이 있어야 실제로 라우팅된다.

### 2.3 키 만료 끄기

같은 메뉴의 **Disable key expiry**. 기본값은 약 6개월 뒤 만료이고, 만료되면
직접 재인증할 때까지 라우팅이 끊긴다. 밖에 있을 때 끊기면 손을 쓸 수 없다.

### 2.4 확인

```bash
tailscale status --json | grep -A2 PrimaryRoutes
```

`PrimaryRoutes: ["192.168.0.0/24"]` 가 나오면 동작 중이다.

---

## 3. 가장 큰 함정 - TUN 모드

**증상**: `tailscale up --advertise-routes` 가 오류 없이 끝나고 `debug prefs` 에도
`AdvertiseRoutes: ["192.168.0.0/24"]` 로 저장되는데, 관리 콘솔에는
`This machine does not expose any routes` 라고 나온다.

`tailscale set`, 패키지 재시작, `--reset` 을 해도 똑같았다.

**원인**: Tailscale 이 **userspace 모드**로 돌고 있었다. 이 모드에서는 서브넷 라우팅이
동작하지 않으므로 광고 자체가 컨트롤 서버에 전달되지 않는다. 조용히 무시된다.

판별은 관리 콘솔의 기기 상세 페이지에서 한다.

```
Debug
TUN Mode      No      <- 이것
Synology Version  7
```

**이유**: DSM 에 `tun` 커널 모듈이 적재되어 있지 않다. 파일은 있는데 로드가 안 된다.

```bash
ls /dev/net/tun          # No such file or directory
ls /lib/modules/tun.ko   # 파일은 존재
```

**해결**:

```bash
sudo insmod /lib/modules/tun.ko
sudo synopkg restart Tailscale
```

`ip link show tailscale0` 로 인터페이스가 생겼는지 확인한다. 그 다음 관리 콘솔을
새로고침하면 `1 route is advertised but not approved` 로 바뀐다.

> 로그를 못 보는 상황에서 헤맸는데, 결국 단서는 관리 콘솔의 `TUN Mode: No` 한 줄이었다.
> 서브넷 라우터가 광고를 안 올릴 때는 여기부터 볼 것.

### 3.1 재부팅 대비

`insmod` 는 재부팅하면 풀린다. 부팅 시 자동 적재하도록 등록해야 한다.

`/usr/local/etc/tun-boot.sh`:

```sh
#!/bin/sh
if [ ! -e /dev/net/tun ]; then
    insmod /lib/modules/tun.ko
    sleep 2
    synopkg restart Tailscale
fi
```

제어판 -> 작업 스케줄러 -> 생성 -> **트리거된 작업** -> 사용자 정의 스크립트

| 항목 | 값 |
|---|---|
| 사용자 | `root` |
| 이벤트 | 부팅됨 |
| 명령 | `/usr/local/etc/tun-boot.sh` |

GUI 로 등록하면 DSM 업데이트 후에도 남는다. `/etc/rc.local` 류는 초기화될 수 있다.

---

## 4. 기존 기기에서 Tailscale 걷어내기

```bash
sudo tailscale logout
sudo systemctl disable --now tailscaled
```

패키지는 남겨 두면 되돌리기 쉽다. 관리 콘솔에서 해당 기기를 Delete 한다.

기기가 오프라인이거나 네트워크가 불안정하면 `logout` 이 서버까지 못 간다.

```
500 Internal Server Error: register request: context deadline exceeded
```

서비스가 꺼졌으면 실질적으로는 같으므로, 콘솔에서 수동으로 지우면 된다.

---

## 5. 남겨야 할 노드

| 노드 | 유지 | 이유 |
|---|:---:|---|
| dsm | O | 서브넷 라우터 |
| 폰 | O | 밖에서 접속하는 쪽 |
| 노트북 | O | 밖에서 접속하는 쪽 |
| 집 안 서버/SBC | X | 서브넷 라우터로 닿는다 |

헷갈리기 쉬운데, **접속하는 쪽에는 Tailscale 이 있어야 한다.** 없애는 것은 집 안에서
접속당하는 쪽이다.

---

## 6. 대역이 겹칠 때 - 4via6

집이 `192.168.0.0/24` 인데 **밖에서 접속하는 장소도 같은 대역**이면 그쪽이 먼저 잡힌다.
로컬 네트워크가 항상 우선하므로 Tailscale 경로로 가지 않는다. 스터디카페, 사무실 등
공유기 기본값을 쓰는 곳은 대부분 이 대역이라 자주 겪는다.

해결은 두 가지다.

| 방법 | 장점 | 단점 |
|---|---|---|
| 집 대역 변경 | 근본적. 이후 신경 쓸 것 없음 | 고정 IP 기기 전부 재설정, 포트포워딩·문서 수정 |
| **4via6** | 집은 그대로. 접속 주소만 추가 | IPv6 주소가 길다 |

4via6 는 Tailscale 이 이 문제를 위해 만든 기능이다. 내부 IPv4 를 전용 IPv6 대역으로
매핑해서 로컬 대역과 겹치지 않게 한다.

### 6.1 설정

주소를 먼저 생성한다. `1` 은 사이트 번호로 임의로 정한다.

```bash
tailscale debug via 1 192.168.0.0/24
# fd7a:115c:a1e0:b1a:0:1:c0a8:0/112
```

기존 경로와 **함께** 광고한다. 집 안에서 쓰던 방식을 유지하기 위해서다.

```bash
tailscale up --advertise-routes=192.168.0.0/24,fd7a:115c:a1e0:b1a:0:1:c0a8:0/112
```

관리 콘솔에서 새 경로를 승인한다. IPv4 때와 같은 절차다.

### 6.2 접속하는 기기 설정

`--accept-routes` 가 꺼져 있으면 경로를 받지 않는다. 노트북·폰 등 **접속하는 쪽**에서 켠다.

```bash
sudo tailscale set --accept-routes
```

`tailscale status` 끝에 이 경고가 있으면 꺼진 것이다.

```
Some peers are advertising routes but --accept-routes is false
```

### 6.3 주소 규칙

마지막 `c0a8:X` 에서 `c0a8` 이 `192.168` 이고 `X` 가 나머지를 **16진수**로 쓴 것이다.

| 내부 IP | 4via6 주소 |
|---|---|
| 192.168.0.3 | `fd7a:115c:a1e0:b1a:0:1:c0a8:3` |
| 192.168.0.7 | `fd7a:115c:a1e0:b1a:0:1:c0a8:7` |
| 192.168.0.16 | `fd7a:115c:a1e0:b1a:0:1:c0a8:10` |
| 192.168.0.172 | `fd7a:115c:a1e0:b1a:0:1:c0a8:ac` |

10 이하는 그대로지만 그 위로는 달라진다. 16 이 `10`, 172 가 `ac` 가 되는 식이다.

### 6.4 이름 붙이기

주소를 외울 수 없으므로 `/etc/hosts` 에 등록한다. **접속하는 기기마다** 넣어야 한다.

```
# tailscale-4via6
fd7a:115c:a1e0:b1a:0:1:c0a8:3    desktop-server-v6
fd7a:115c:a1e0:b1a:0:1:c0a8:7    ender-5-v6
fd7a:115c:a1e0:b1a:0:1:c0a8:8    ender-3v3-v6
fd7a:115c:a1e0:b1a:0:1:c0a8:9    rpi-cm4-v6
fd7a:115c:a1e0:b1a:0:1:c0a8:10   desktop-minho-v6
fd7a:115c:a1e0:b1a:0:1:c0a8:ac   dsm-v6
# end-4via6
```

기기를 추가하려면 이 블록에 한 줄 넣으면 된다. 폰은 hosts 파일이 없으므로 주소를
직접 입력하거나 앱의 즐겨찾기에 저장한다.

### 6.5 사용

```bash
ssh minodori@ender-5-v6        # 밖에서 (대역이 겹쳐도 됨)
ssh minodori@192.168.0.7       # 집에서
```

둘 다 살아 있으므로 상황에 맞게 쓰면 된다. RDP 도 Remmina 에 `desktop-server-v6` 로
등록하면 된다.

---

## 7. 관련 작업 - 공유기 초기화 후 복구

펌웨어 업그레이드로 메시 설정과 포트포워딩이 초기화되어 같이 정리했다.

### 7.1 포트포워딩은 내부도 같은 번호로

```
외부 80  -> 내부 80
외부 443 -> 내부 443
```

외부 443 을 내부 5001(DSM 포털)로 바로 보내면 **nginx 의 호스트 이름 분기를 건너뛴다.**
`www.yirugeo.com/telegram/webhook.php` 가 404 가 되고 텔레그램 봇이 죽는다.

내부 443 의 nginx 가 Host 헤더를 보고 갈라 준다.

```
www.yirugeo.com  -> Web Station
dsm.yirugeo.com  -> DSM 포털 (내부적으로 5001 로 전달)
git.yirugeo.com  -> GitLab
```

리버스 프록시에 적힌 5001 과 라우터 포워딩의 443 이 달라 보이지만 층이 다른 것이라
정상이다. 5001 은 NAS 안에서만 오간다.

### 7.2 80 포트는 유지해야 한다

Let's Encrypt 갱신(HTTP-01)이 `http://도메인/.well-known/acme-challenge/` 로 확인한다.
80 을 막으면 90일 뒤 인증서가 만료된다. DNS-01 로 바꾸면 닫을 수 있다.

### 7.3 텔레그램 웹훅은 포트가 제한된다

**443, 80, 88, 8443** 만 받는다. 443 을 임의 포트로 옮기면 웹훅을 등록할 수 없다.

---

## 8. 관련 작업 - 무선 지연

SBC 들이 5GHz 에 붙지 않거나 ping 이 튀는 문제를 같이 잡았다.

### 8.1 netplan 의 band 키

```yaml
access-points:
  "5168ap":
    auth:
      key-management: "psk"
      password: "..."
      band: 5GHz        # 잘못된 위치. auth 안에 있으면 안 된다
```

`unknown key 'band'` 오류가 난다. `band` 는 `auth` 와 같은 층이다. netplan 버전이
낮으면 아예 지원하지 않는다.

**그런데 이 경우엔 키 자체가 불필요했다.** 공유기가 대역별로 SSID 를 나눠 두었다.

```
5168ap        5745MHz  (5GHz 전용)
5168ap2.4G    2432MHz  (2.4GHz)
```

SSID 가 이미 대역을 특정하므로 `band` 줄을 지우니 바로 붙었다.

### 8.2 노트북 WiFi 절전 - 프로필마다 따로 걸린다

ping 이 1.7ms 와 117ms 를 오가고 손실 12.5% 가 났다. 같은 기기에 유선/무선 두 경로로
재어 구간을 갈랐다.

| 경로 | 평균 | 손실 |
|---|---:|---:|
| 유선 192.168.88.3 | 0.26ms | 0% |
| 무선 192.168.0.8 | 487ms | 75% |

노트북(MediaTek MT7925)의 WiFi 절전이었다. work11.md §6.23 과 같은 원인이다.

**함정은 NetworkManager 가 절전 설정을 연결 프로필마다 따로 관리한다는 것이다.**

```bash
nmcli con mod 5168ap 802-11-wireless.powersave 2    # 이 WiFi 에만 적용된다
```

집 WiFi 에만 걸어 두었더니 다른 장소의 WiFi 에 붙을 때마다 절전이 되살아났다.
프로필 목록을 보면 명확하다.

```
5168ap          disable
mesh5168        disable
Z_studycafe     default     <- 나머지 전부 기본값
AIE_509_5G      default
...
```

전역 기본값으로 두어야 새로 붙는 WiFi 에도 자동 적용된다.

`/etc/NetworkManager/conf.d/wifi-powersave.conf`:

```ini
[connection]
wifi.powersave = 2
```

```bash
sudo systemctl reload NetworkManager
```

**결과**:

| 시점 | 평균 | 최대 | 손실 |
|---|---:|---:|---:|
| 절전 켜짐 | 144ms | 414ms | 12.5% |
| 프로필만 해제 (다른 WiFi) | 3.5ms | 21ms | 0% |
| 전역 해제 | 3.3ms | 6.5ms | 0% |

40회 중 10ms 를 넘는 값이 하나도 없다.

> ASPM(`mt7925e` 의 `disable_aspm=1`)도 후보로 보았으나 건드릴 필요가 없었다.
> PCIe 전력 관리는 WiFi 절전과 다른 층이므로, 절전을 껐는데도 남으면 그때 볼 것.

> **판별법** (work11.md §6.23): 지연이 일정 폭으로 늘다 뚝 떨어지는 톱니면 절전이다.
> 불규칙하게 튀면 간섭이나 드라이버다.

---

## 9. 확인 명령 모음

```bash
# 서브넷 라우터 동작 확인 (DSM). 승인된 경로가 모두 나와야 한다
tailscale status --json | grep -A5 AllowedIPs

# 접속하는 기기에서 경로를 받는지 (이 경고가 있으면 --accept-routes 가 꺼진 것)
tailscale status | grep -A2 "Health check"

# 4via6 통신 확인
ping6 -c 3 dsm-v6

# TUN 모드 확인
ls /dev/net/tun
ip link show tailscale0

# 무선 절전 확인
iw dev wlan0 get power_save
cat /etc/NetworkManager/conf.d/wifi-powersave.conf      # 전역
nmcli -g 802-11-wireless.powersave con show <연결이름>  # 프로필별

# 프로필 전체 훑기 (빠진 것 찾기)
for c in $(nmcli -t -f NAME,TYPE con show | grep wireless | cut -d: -f1); do
    printf "%-20s %s\n" "$c" "$(nmcli -g 802-11-wireless.powersave con show "$c")"
done

# 구간 분리 측정 (유선/무선 주소를 다 가진 기기로)
ping -c 10 192.168.88.3    # 유선
ping -c 10 192.168.0.8     # 무선
```
