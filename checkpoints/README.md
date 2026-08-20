# checkpoints — 학습된 정책 가중치

대회 운영규정 제9조 제2항 제3호는 자체 개발 모델의 가중치를 **승인 절차 없이
누구나 접근할 수 있는 공개저장소에 게시**할 것을 요구합니다. 여기가 그 위치입니다.

| 파일 | 내용 |
|---|---|
| `policy.zip` | Stable-Baselines3 PPO 정책 |
| `vecnormalize.pkl` | 관측 정규화 통계 — **없으면 정책이 동작하지 않습니다** |

```bash
uv run python -m rl.eval --run checkpoints --render
```

> 최종 학습 결과 하나만 커밋합니다. git 은 바이너리를 영구 보존하므로 매 실험을
> 커밋하면 `--depth 1` 클론이 무거워집니다. 중간 버전이 필요하면 GitHub Releases 를
> 사용하십시오.
