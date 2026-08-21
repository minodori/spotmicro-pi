"""PPO 학습.

    python -m rl.train --obs B --timesteps 20000000 --num-envs 12

관측 A안/B안을 같은 조건에서 돌려 성능 차를 잰다. 그 차이가 피드백 센서를
추가할지 판단하는 근거가 된다.

병렬 환경 수는 물리 코어의 0.7~0.8 배가 가장 빠르다. 그 이상은 학습 스텝과
시뮬레이션이 코어를 두고 경쟁해 오히려 느려진다. `OMP_NUM_THREADS=1` 을 함께
지정할 것 — 없으면 워커마다 스레드를 코어 수만큼 띄워 서로 잡아먹는다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from rl.envs import config as C
from rl.envs.spotmicro_walk import SpotMicroWalkEnv

PPO_KWARGS = dict(
    policy="MlpPolicy",
    learning_rate=3e-4,
    n_steps=512,
    batch_size=2048,
    n_epochs=5,
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    ent_coef=0.005,
    vf_coef=0.5,
    max_grad_norm=1.0,
    policy_kwargs=dict(
        net_arch=dict(pi=[256, 128], vf=[256, 128]),
        # 초기 행동 표준편차 exp(-2.0)=0.135.  **기본값 0(=std 1.0)이면 학습이 성립하지
        # 않는다.** std 1.0 은 12개 관절이 매 스텝 ±14도(ACTION_SCALE)씩 독립적으로
        # 튄다는 뜻이고, 이 로봇의 기립 자세는 다리 도달의 88%까지 뻗어 있어
        # 0.5초 만에 기울기 종료에 걸린다.
        #
        # 문제는 생존 시간이 아니라 **부호**다. 그 상태에서 스텝당 순보상이 음수라
        # 에피소드를 끝내는 것이 이득이 되고, 정책은 "빨리 넘어지기"로 수렴한다.
        # 80만 스텝을 돌려 ep_len_mean 이 10~14 에 고착하는 것으로 실제로 확인했다.
        #
        #   초기 std   생존      순보상/스텝
        #     1.00      25 스텝    -2.40      <- 끝내는 것이 이득
        #     0.37      39 스텝    -1.27
        #     0.135    515 스텝    +0.27      <- 부호가 뒤집힘
        #     0.05     660 스텝    +1.24      (탐색이 좁아 보행 미발견 위험)
        log_std_init=-2.0,
    ),
)


def make_env(rank: int, seed: int, obs_mode: str, domain_rand: bool):
    def _init():
        return Monitor(SpotMicroWalkEnv(obs_mode=obs_mode,
                                        domain_rand=domain_rand,
                                        seed=seed + rank))
    return _init


def main() -> None:
    p = argparse.ArgumentParser(description="SpotMicro 보행 정책 PPO 학습")
    p.add_argument("--obs", choices=["A", "B"], default="B",
                   help="A: 관절 피드백 포함(45) / B: 제외, 행동 이력(69)")
    p.add_argument("--timesteps", type=int, default=20_000_000)
    p.add_argument("--num-envs", type=int, default=12)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--run-name", type=str, default=None)
    p.add_argument("--no-domain-rand", action="store_true")
    p.add_argument("--resume", type=str, default=None)
    p.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda", "auto"],
                   help="기본 cpu. 정책이 작은 MLP 라 GPU 전송 오버헤드가 더 크고, "
                        "물리 연산도 CPU 에서 돈다")
    args = p.parse_args()

    run_dir = Path("rl/runs") / (args.run_name or f"obs{args.obs}")
    run_dir.mkdir(parents=True, exist_ok=True)
    dr = not args.no_domain_rand

    vec = SubprocVecEnv if args.num_envs > 1 else DummyVecEnv
    env = vec([make_env(i, args.seed, args.obs, dr) for i in range(args.num_envs)])

    # 관측 정규화 통계는 배포 시에도 필요하다. 이어서 학습할 때 새로 만들면
    # 관측 분포가 갑자기 바뀌어 정책이 무너지므로 반드시 함께 불러온다.
    stats = None
    if args.resume:
        for cand in (Path(args.resume).with_name("vecnormalize.pkl"),
                     run_dir / "vecnormalize.pkl"):
            if cand.exists():
                stats = cand
                break
    if stats is not None:
        env = VecNormalize.load(str(stats), env)
        env.training, env.norm_reward = True, True
        print(f"정규화 통계 복원: {stats}")
    else:
        if args.resume:
            print("경고: vecnormalize 통계를 찾지 못했습니다. 재개 직후 성능이 떨어집니다.")
        env = VecNormalize(env, norm_obs=True, norm_reward=True,
                           clip_obs=10.0, gamma=PPO_KWARGS["gamma"])

    if args.resume:
        model = PPO.load(args.resume, env=env, device=args.device,
                         tensorboard_log=str(run_dir))
        print(f"이어서 학습: {args.resume}")
    else:
        model = PPO(env=env, verbose=1, seed=args.seed, device=args.device,
                    tensorboard_log=str(run_dir), **PPO_KWARGS)

    ckpt = CheckpointCallback(save_freq=max(500_000 // args.num_envs, 1),
                              save_path=str(run_dir / "checkpoints"),
                              name_prefix="policy", save_vecnormalize=True)

    print(f"관측 {args.obs}안 ({C.obs_dim(args.obs)}차원) | 환경 {args.num_envs}개 | "
          f"랜덤화 {'ON' if dr else 'OFF'} | 목표 {args.timesteps:,} 스텝 | "
          f"제어 {C.CONTROL_HZ:.0f}Hz | device={args.device}")
    model.learn(total_timesteps=args.timesteps, callback=ckpt, progress_bar=False)

    model.save(run_dir / "policy")
    env.save(str(run_dir / "vecnormalize.pkl"))
    print(f"\n저장 완료\n  {run_dir / 'policy.zip'}\n  {run_dir / 'vecnormalize.pkl'}")
    print(f"\n평가:  python -m rl.eval --run {run_dir} --command 0.2 0 0")


if __name__ == "__main__":
    main()
