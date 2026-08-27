"""학습된 정책이 걷는 것을 영상 파일로 남긴다. 1920x1080 / 30fps.

    MUJOCO_GL=egl uv run python -m rl.render_policy --out docs/media/cut21_policy.mp4

`rl.eval --render` 는 창을 띄우기만 해서 파일이 남지 않는다. 시연 영상 21번 컷은
정책이 실제로 걷는 화면이 필요하므로 오프스크린으로 그려 mp4 로 쓴다.

화면에 글자를 넣지 않는다 — 자막은 편집에서 붙는다. render_cuts.py 와 같은 규칙이다.

무릎 각속도를 함께 반환한다. 이 컷의 요지가 "빠르지만 서보가 못 따라간다" 이므로
편집에서 쓸 수치를 로그로 남겨 둔다.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FPS = 30
W, H = 1920, 1080


def camera(dist, azim, elev, look):
    import mujoco
    c = mujoco.MjvCamera()
    c.type = mujoco.mjtCamera.mjCAMERA_FREE
    c.distance, c.azimuth, c.elevation = dist, azim, elev
    c.lookat[:] = look
    return c


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run", default="checkpoints")
    p.add_argument("--out", default="docs/media/cut21_policy.mp4")
    p.add_argument("--seconds", type=float, default=12.0)
    p.add_argument("--command", type=float, nargs=3, default=[0.3, 0.0, 0.0])
    a = p.parse_args()

    import warnings
    warnings.filterwarnings("ignore")
    import mujoco
    import imageio.v2 as imageio
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from rl.envs.spotmicro_walk import SpotMicroWalkEnv
    from rl.envs import config as C
    import rl.model_api as M

    def mk():
        return SpotMicroWalkEnv(obs_mode="B", domain_rand=False, seed=0)

    env = VecNormalize.load(f"{a.run}/vecnormalize.pkl", DummyVecEnv([mk]))
    env.training = False
    env.norm_reward = False
    model = PPO.load(f"{a.run}/policy.zip")
    raw = env.venv.envs[0].unwrapped

    knee = [M.JOINT_ORDER.index(f"{l}_foot") for l in M.LEGS]
    tid = mujoco.mj_name2id(raw.model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    r = mujoco.Renderer(raw.model, H, W)

    obs = env.reset()
    raw._command = np.array(a.command, dtype=np.float64)
    prev = raw.data.qpos[7:].copy()
    frames, slew = [], []

    for _ in range(int(a.seconds * FPS)):
        act, _ = model.predict(obs, deterministic=True)
        obs, _, done, _ = env.step(act)
        q = raw.data.qpos[7:]
        slew.append(np.degrees(np.abs(q[knee] - prev[knee]).max()) / C.CONTROL_DT)
        prev = q.copy()
        raw._command = np.array(a.command, dtype=np.float64)

        look = raw.data.xpos[tid].copy()
        look[2] -= 0.06
        r.update_scene(raw.data, camera=camera(0.66, 128, -10, look))
        frames.append(r.render())
        if done[0]:
            obs = env.reset()
            raw._command = np.array(a.command, dtype=np.float64)
            prev = raw.data.qpos[7:].copy()
    r.close()

    imageio.mimwrite(a.out, frames, fps=FPS, quality=9, macro_block_size=1)
    s = np.array(slew)
    print(f"  {a.out}  {len(frames)}프레임 {len(frames)/FPS:.1f}초")
    print(f"  무릎 각속도  최대 {s.max():.0f}°/s (정격 500 의 {s.max()/500*100:.0f}%)"
          f"  중앙 {np.median(s):.0f}  정격 초과 스텝 {100*(s>500).mean():.1f}%")


if __name__ == "__main__":
    main()
