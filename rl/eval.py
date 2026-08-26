"""학습된 정책 평가 — **학습 없이, GPU 없이** 실행된다.

대회 2차 기능테스트에서 심사자가 하드웨어 없이 결과를 재현하는 경로다.

    python -m rl.eval --run checkpoints --command 0.2 0 0   # 배포된 가중치
    python -m rl.eval --run checkpoints --render
    python -m rl.eval --run rl/runs/obsA --command 0.2 0 0   # 직접 학습한 것

출력 지표는 결과보고서에 그대로 인용할 수 있게 구성했다. 특히 **최대 서보 토크**와
**무릎 각속도**는 학습된 정책이 실물 서보가 낼 수 없는 명령을 내는지 판정한다.
규칙 기반과 달리 정책의 명령은 예측 불가능하므로, 실물에 올리기 전에 여기서 거른다.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from rl import model_api as M
from rl.envs import config as C
from rl.envs.spotmicro_walk import SpotMicroWalkEnv

from Common.servo_map import SERVO_RATED_SLEW   # 6V 에서 500도/s


def _obs_mode_of(run: Path) -> str:
    """정책이 기대하는 관측 모드는 학습이 남긴 meta.json 이 정본이다.

    디렉터리 이름으로 추측하면(`endswith("A")`) 가중치를 checkpoints/ 로 옮기는
    순간 틀린 모드로 읽고, 관측 차원이 달라 로드 자체가 실패하거나 더 나쁘게는
    엉뚱한 값을 넣은 채 조용히 돌아간다.
    """
    meta = run / "meta.json"
    if meta.exists():
        return json.loads(meta.read_text(encoding="utf-8"))["obs_mode"]
    guess = "A" if run.name.endswith("A") else "B"
    print(f"경고: {meta} 가 없어 디렉터리 이름으로 {guess}안이라고 추측합니다. "
          f"틀렸다면 --obs 로 지정하세요.")
    return guess


def load(run: Path, obs_mode: str, render: bool, domain_rand: bool):
    env = DummyVecEnv([lambda: SpotMicroWalkEnv(
        obs_mode=obs_mode, render_mode="human" if render else None,
        domain_rand=domain_rand, seed=0)])
    stats = run / "vecnormalize.pkl"
    if stats.exists():
        env = VecNormalize.load(str(stats), env)
        env.training, env.norm_reward = False, False
    else:
        print(f"경고: {stats} 없음. 정규화 없이 평가하면 결과가 크게 달라집니다.")

    policy = run / "policy.zip"
    if not policy.exists():
        cks = sorted((run / "checkpoints").glob("policy_*_steps.zip"))
        if not cks:
            raise SystemExit(f"{run} 에서 정책을 찾지 못했습니다.")
        policy = cks[-1]
        print(f"최종 정책이 없어 마지막 체크포인트 사용: {policy.name}")
    return PPO.load(str(policy), device="cpu"), env


def rollout(model, env, command, episodes, render):
    raw = env.venv.envs[0].unwrapped if hasattr(env, "venv") else env.envs[0].unwrapped
    out = []
    for _ in range(episodes):
        obs = env.reset()
        if command is not None:
            raw._command = np.array(command, dtype=np.float64)

        vx, vy, wz, h, tau, slew = [], [], [], [], [], []
        prev_q = raw.data.qpos[7:].copy()
        infer_ns, steps = 0, 0
        while True:
            t0 = time.perf_counter_ns()
            act, _ = model.predict(obs, deterministic=True)
            infer_ns += time.perf_counter_ns() - t0

            obs, _, done, _ = env.step(act)
            steps += 1

            v = raw._base_lin_vel()
            vx.append(v[0]); vy.append(v[1]); wz.append(raw._base_ang_vel()[2])
            h.append(raw.data.qpos[2])
            tau.append(np.abs(raw.data.actuator_force).max())
            q = raw.data.qpos[7:]
            # 무릎(각 다리의 foot 관절)이 정격을 넘는지
            knee = [M.JOINT_ORDER.index(f"{leg}_foot") for leg in M.LEGS]
            slew.append(np.degrees(np.abs(q[knee] - prev_q[knee]).max()) / C.CONTROL_DT)
            prev_q = q.copy()

            if command is not None:
                raw._command = np.array(command, dtype=np.float64)
            if render:
                time.sleep(max(0.0, C.CONTROL_DT - 1e-4))
            if done[0]:
                break

        out.append(dict(dur=steps * C.CONTROL_DT, vx=float(np.mean(vx)),
                        vy=float(np.mean(vy)), wz=float(np.mean(wz)),
                        h=float(np.mean(h)), h_sd=float(np.std(h)),
                        tau=float(np.max(tau)), slew=float(np.max(slew)),
                        infer_ms=infer_ns / steps / 1e6))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="SpotMicro 보행 정책 평가")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--obs", choices=["A", "B"], default=None,
                   help="생략하면 run/meta.json 에서 읽음")
    p.add_argument("--episodes", type=int, default=5)
    p.add_argument("--render", action="store_true")
    p.add_argument("--command", type=float, nargs=3, metavar=("VX", "VY", "WZ"))
    p.add_argument("--no-domain-rand", action="store_true")
    args = p.parse_args()

    obs_mode = args.obs or _obs_mode_of(args.run)
    model, env = load(args.run, obs_mode, args.render, not args.no_domain_rand)
    r = rollout(model, env, args.command, args.episodes, args.render)

    mean = lambda k: float(np.mean([x[k] for x in r]))
    done = sum(x["dur"] >= C.EPISODE_LENGTH_S - 1e-6 for x in r)
    print(f"\n{'='*70}")
    print(f" {args.run}   관측 {obs_mode}안   명령 {args.command or '무작위'}   "
          f"랜덤화 {'OFF' if args.no_domain_rand else 'ON'}")
    print(f"{'='*70}")
    print(f"{'ep':>3} {'생존s':>7} {'vx m/s':>9} {'vy m/s':>9} {'wz r/s':>9} "
          f"{'높이mm':>8} {'토크Nm':>8} {'슬루°/s':>9}")
    for i, x in enumerate(r):
        print(f"{i:3d} {x['dur']:7.2f} {x['vx']:9.3f} {x['vy']:9.3f} {x['wz']:9.3f} "
              f"{x['h']*1000:8.1f} {x['tau']:8.3f} {x['slew']:9.0f}")
    print("-" * 70)
    print(f"평균 생존       {mean('dur'):.2f} s  (완주 {done}/{len(r)})")
    print(f"평균 전진 속도  {mean('vx'):.3f} m/s")
    print(f"동체 높이       {mean('h')*1000:.1f} mm  "
          f"(σ {mean('h_sd')*1000:.1f}, 목표 {M.standingTrunkHeight()*1000:.0f})")
    mx_slew = max(x["slew"] for x in r)
    print(f"최대 무릎 각속도 {mx_slew:.0f} °/s  "
          f"(DS3235 정격 {SERVO_RATED_SLEW:.0f} 의 {mx_slew/SERVO_RATED_SLEW*100:.0f}%)"
          + ("   ⚠ 실물 이식 불가" if mx_slew > SERVO_RATED_SLEW else ""))
    print(f"최대 서보 토크  {max(x['tau'] for x in r):.3f} N·m")
    print(f"정책 추론 시간  {mean('infer_ms'):.3f} ms/스텝  "
          f"(제어 주기 {C.CONTROL_DT*1000:.0f} ms 의 "
          f"{mean('infer_ms')/(C.CONTROL_DT*1000)*100:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
