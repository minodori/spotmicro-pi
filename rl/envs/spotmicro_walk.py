"""SpotMicro 속도 명령 추종 보행 환경 (MuJoCo + Gymnasium).

정책은 속도 명령(vx, vy, wz)을 받아 12개 관절의 **각도**를 출력한다. 토크가 아니다 —
실물은 PCA9685 가 구동하는 위치제어 서보라 토크 명령을 받을 수 없고, 각도로 두면
학습 결과를 `model_api.qposToServo()` 에 그대로 넘길 수 있다.

기구 상수·기립 자세·가동 범위는 **여기에 복제하지 않고** `rl.model_api` 에서 읽는다.
같은 표를 두 곳에 두면 반드시 어긋난다 (docs/업무분장.md 1장에 사례 셋).

관측을 두 가지로 두고 비교한다. 취미용 서보는 관절 위치를 되읽을 수 없어 4족보행
강화학습의 표준 관측인 관절각·관절각속도를 실물에서 얻을 수 없기 때문이다.
그 차이가 곧 피드백 센서를 추가할지 판단하는 근거가 된다.

    A안 (45)  ... 관절각 12 + 관절각속도 12 를 포함. 실물에는 없는 정보
    B안 (69)  ... 그 자리에 이전 행동 5프레임. 실물에서 그대로 재현 가능

B안에서는 시뮬레이터에서도 `data.qpos` 를 쓰지 않는다. 시뮬에만 있는 정보를 주고
학습하면 이식이 실패한다.
"""

from __future__ import annotations

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

from rl import model_api as M
from rl.envs import config as C


class SpotMicroWalkEnv(gym.Env):
    """속도 명령을 추종하는 4족 보행 환경.

    Parameters
    ----------
    obs_mode : {"A", "B"}
        A 는 관절 피드백을 포함(45차원), B 는 제외하고 행동 이력으로 대체(69차원).
    """

    metadata = {"render_modes": ["human"], "render_fps": int(C.CONTROL_HZ)}

    def __init__(
        self,
        obs_mode: str = "B",
        render_mode: str | None = None,
        domain_rand: bool = True,
        seed: int | None = None,
    ) -> None:
        super().__init__()
        if obs_mode not in ("A", "B"):
            raise ValueError(f"obs_mode 는 'A' 또는 'B' 여야 합니다: {obs_mode!r}")
        self.obs_mode = obs_mode

        self.model = mujoco.MjModel.from_xml_path(M.MJCF_SCENE)
        self.data = mujoco.MjData(self.model)
        self._check_model()

        # --- model_api 에서 읽는다. 복제 금지 ---
        self.default_qpos = M.standingQpos()          # (12,) 기립 자세
        self.target_height = M.standingTrunkHeight()  # 보상 base_height 목표
        self.joint_range = M.jointRanges(self.model)  # (12,2)

        self.action_space = spaces.Box(-1.0, 1.0, (12,), np.float32)
        self.observation_space = spaces.Box(
            -np.inf, np.inf, (C.obs_dim(obs_mode),), np.float32)

        self.render_mode = render_mode
        self.domain_rand = domain_rand
        self._rng = np.random.default_rng(seed)
        self._viewer = None

        self._cache_ids()
        self._nominal = dict(
            mass=float(self.model.body_mass[self._trunk_bid]),
            friction=self.model.geom_friction.copy(),
            gain=self.model.actuator_gainprm.copy(),
            bias=self.model.actuator_biasprm.copy(),
            com=self.model.body_ipos[self._trunk_bid].copy(),
        )
        self._max_steps = int(C.EPISODE_LENGTH_S * C.CONTROL_HZ)
        self._push_every = int(C.PUSH_INTERVAL_S * C.CONTROL_HZ)
        self._reset_internals()

    # ------------------------------------------------------------------ 검증
    def _check_model(self) -> None:
        """어긋난 채로 학습이 돌아가는 사고를 막는다."""
        if self.model.nu != 12:
            raise ValueError(f"액추에이터가 12개가 아닙니다: {self.model.nu}")
        for i, name in enumerate(M.JOINT_ORDER):
            jid = self.model.actuator_trnid[i, 0]
            actual = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, jid)
            if actual != name:
                raise ValueError(
                    f"액추에이터 {i} 가 '{actual}' 을 구동합니다. "
                    f"model_api.JOINT_ORDER 는 '{name}' 을 기대합니다.\n"
                    "순서가 어긋나면 학습한 정책을 실물에 보낼 수 없습니다.")
        if not (self.model.actuator_biasprm[:, 1] < 0).all():
            raise ValueError(
                "액추에이터가 위치 제어가 아닙니다. 실물은 토크 명령을 받을 수 "
                "없으므로 <position> 이어야 합니다.")

    def _cache_ids(self) -> None:
        name2id = lambda t, n: mujoco.mj_name2id(self.model, t, n)
        self._trunk_bid = name2id(mujoco.mjtObj.mjOBJ_BODY, "trunk")
        self._floor_gid = name2id(mujoco.mjtObj.mjOBJ_GEOM, "floor")
        if self._floor_gid < 0:
            self._floor_gid = name2id(mujoco.mjtObj.mjOBJ_GEOM, "ground")
        self._foot_gids = np.array([
            name2id(mujoco.mjtObj.mjOBJ_GEOM, f"{leg}_foot") for leg in M.LEGS])
        if (self._foot_gids < 0).any():   # 이름 규칙이 다르면 site 로 대체 탐색
            self._foot_gids = np.array([
                g for g in range(self.model.ngeom)
                if (n := mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, g))
                and any(n.startswith(leg) and "foot" in n for leg in M.LEGS)])
        self._body_gids = {
            g for g in range(self.model.ngeom)
            if g not in self._foot_gids and g != self._floor_gid}

    # ------------------------------------------------------------------ 상태
    def _reset_internals(self) -> None:
        self._step_count = 0
        self._command = np.zeros(3)
        self._last_action = np.zeros(12)
        self._action_hist = [np.zeros(12) for _ in range(C.HIST_FRAMES)]
        self._feet_air_time = np.zeros(4)
        self._last_contact = np.ones(4, dtype=bool)
        self._first_contact = np.zeros(4, dtype=bool)
        self._air_at_contact = np.zeros(4)
        self._joint_offset = np.zeros(12)
        self._latency = 0
        self._delay_buf: list[np.ndarray] = []

    def _sample_command(self) -> np.ndarray:
        if self._rng.random() < C.CMD_ZERO_PROB:
            return np.zeros(3)
        return np.array([self._rng.uniform(*C.CMD_VX),
                         self._rng.uniform(*C.CMD_VY),
                         self._rng.uniform(*C.CMD_WZ)])

    def _randomize(self) -> None:
        """실물과 시뮬이 다를 수 있는 것들을 흔든다. 폭은 실측 근거가 있다."""
        if not self.domain_rand:
            self._latency, self._joint_offset[:] = 0, 0.0
            return
        m, n = self.model, self._nominal
        m.body_mass[self._trunk_bid] = n["mass"] + self._rng.uniform(*C.RAND_TRUNK_MASS)
        m.geom_friction[:, 0] = n["friction"][:, 0] * self._rng.uniform(*C.RAND_FRICTION)
        kp = self._rng.uniform(*C.RAND_KP)
        m.actuator_gainprm[:, 0] = n["gain"][:, 0] * kp
        m.actuator_biasprm[:, 1] = n["bias"][:, 1] * kp
        m.body_ipos[self._trunk_bid] = n["com"] + [
            self._rng.uniform(*C.RAND_COM_X) * 0.001, 0.0, 0.0]
        # 혼이 스플라인에 한 칸 어긋나면 14.4도 튄다. 그런 로봇을 본 적 없는
        # 정책은 실물에서 그걸 만나면 넘어진다.
        self._joint_offset = np.radians(
            self._rng.normal(0.0, C.RAND_SERVO_OFFSET_DEG, 12))
        self._latency = int(self._rng.integers(0, C.RAND_LATENCY_MAX + 1))

    # ------------------------------------------------------------------ gym
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        mujoco.mj_resetData(self.model, self.data)
        self._reset_internals()
        self._randomize()

        self.data.qpos[0:3] = [0.0, 0.0, self.target_height + 0.02]
        self.data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
        self.data.qpos[7:] = self.default_qpos + self._rng.uniform(-0.05, 0.05, 12)
        self.data.qvel[:] = 0.0
        self.data.ctrl[:] = self.default_qpos
        mujoco.mj_forward(self.model, self.data)

        self._command = self._sample_command()
        self._delay_buf = [np.zeros(12) for _ in range(self._latency + 1)]
        return self._get_obs(), {}

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)

        # 제어 지연 — 지금 낸 명령이 latency 스텝 뒤에 반영된다
        self._delay_buf.append(action)
        applied = self._delay_buf.pop(0)

        target = self.default_qpos + C.ACTION_SCALE * applied + self._joint_offset
        self.data.ctrl[:] = np.clip(target, self.joint_range[:, 0], self.joint_range[:, 1])
        for _ in range(C.DECIMATION):
            mujoco.mj_step(self.model, self.data)

        self._step_count += 1
        self._update_air_time()

        reward, terms = self._reward(action)
        terminated = self._terminated()
        truncated = self._step_count >= self._max_steps
        if terminated:
            reward -= C.FALL_PENALTY

        if self.domain_rand and self._step_count % self._push_every == 0:
            self.data.qvel[0:2] += self._rng.uniform(-C.PUSH_VEL, C.PUSH_VEL, 2)

        self._last_action = action
        self._action_hist.append(action)
        self._action_hist.pop(0)

        if self.render_mode == "human":
            self.render()
        return (self._get_obs(), float(reward), bool(terminated), bool(truncated),
                {"reward_terms": terms, "command": self._command.copy()})

    # ------------------------------------------------------------------ 관측
    def _rot(self) -> np.ndarray:
        return self.data.xmat[self._trunk_bid].reshape(3, 3)

    def _projected_gravity(self) -> np.ndarray:
        """동체 좌표계에서 본 중력. 수평이면 (0, 0, -1). IMU 가속도계로 대체 가능."""
        return self._rot().T @ np.array([0.0, 0.0, -1.0])

    def _base_lin_vel(self) -> np.ndarray:
        """보상·종료에만 쓴다. 실물에서 얻을 수 없어 관측에는 넣지 않는다."""
        return self._rot().T @ self.data.qvel[0:3]

    def _base_ang_vel(self) -> np.ndarray:
        return self.data.qvel[3:6].copy()          # free joint 는 동체 좌표계

    def _get_obs(self) -> np.ndarray:
        common = [self._base_ang_vel() * C.SCALE_ANG_VEL,
                  self._projected_gravity(),
                  self._command]
        if self.obs_mode == "A":
            parts = common + [self.data.qpos[7:] - self.default_qpos,
                              self.data.qvel[6:] * C.SCALE_JOINT_VEL,
                              self._last_action]
        else:
            # 관절 상태를 명령 이력에서 암묵 추정하게 한다.
            # data.qpos 를 쓰면 실물에 없는 정보로 학습하는 것이 된다.
            parts = common + list(self._action_hist)
        return np.concatenate(parts).astype(np.float32)

    # ------------------------------------------------------------------ 접촉
    def _foot_contacts(self) -> np.ndarray:
        c = np.zeros(4, dtype=bool)
        for i in range(self.data.ncon):
            con = self.data.contact[i]
            if self._floor_gid not in (con.geom1, con.geom2):
                continue
            other = con.geom1 if con.geom2 == self._floor_gid else con.geom2
            hit = np.where(self._foot_gids == other)[0]
            if hit.size:
                c[hit[0]] = True
        return c

    def _undesired_contacts(self) -> int:
        n = 0
        for i in range(self.data.ncon):
            con = self.data.contact[i]
            if self._floor_gid not in (con.geom1, con.geom2):
                continue
            other = con.geom1 if con.geom2 == self._floor_gid else con.geom2
            if other in self._body_gids:
                n += 1
        return n

    def _update_air_time(self) -> None:
        contact = self._foot_contacts()
        self._first_contact = contact & ~self._last_contact
        self._air_at_contact = self._feet_air_time.copy()
        self._feet_air_time = np.where(contact, 0.0, self._feet_air_time + C.CONTROL_DT)
        self._last_contact = contact

    # ------------------------------------------------------------------ 보상
    def _reward(self, action) -> tuple[float, dict]:
        w = C.REWARD
        v, om, g = self._base_lin_vel(), self._base_ang_vel(), self._projected_gravity()
        lin_err = np.sum((self._command[:2] - v[:2]) ** 2)
        ang_err = (self._command[2] - om[2]) ** 2

        t = {
            # sigma 는 명령 범위에 맞춰야 한다. 넓으면 "가만히 서 있기" 가
            # 최적해가 되어 2천만 스텝을 태우고도 전진 0 이 나온다.
            "track_lin": w["track_lin"] * np.exp(-lin_err / C.TRACKING_SIGMA),
            "track_ang": w["track_ang"] * np.exp(-ang_err / C.TRACKING_SIGMA),
            "lin_vel_z": w["lin_vel_z"] * v[2] ** 2,
            "ang_vel_xy": w["ang_vel_xy"] * np.sum(om[:2] ** 2),
            "orientation": w["orientation"] * np.sum(g[:2] ** 2),
            "base_height": w["base_height"]
            * (self.data.qpos[2] - self.target_height) ** 2,
            "torque": w["torque"] * np.sum(self.data.actuator_force ** 2),
            "joint_accel": w["joint_accel"] * np.sum(self.data.qacc[6:] ** 2),
            "action_rate": w["action_rate"] * np.sum((action - self._last_action) ** 2),
            # 이 항이 없으면 12개 관절이 전부 행동 한계에 붙어 굳는다.
            # 클리핑 경계에서는 기울기가 사라져 빠져나오지 못한다.
            "action_mag": w["action_mag"] * np.sum(action ** 2),
            "joint_limit": w["joint_limit"] * self._limit_violation(),
            "air_time": w["air_time"] * self._air_time_reward(),
            "undesired": w["undesired"] * self._undesired_contacts(),
            "alive": w["alive"],
        }
        total = sum(t.values())
        # 음의 항 합이 양의 항을 넘으면 **에피소드를 끝내는 것이 이득**이 된다.
        # 페널티는 살아 있는 동안만 쌓이므로, 정책은 보행이 아니라 조기 종료를
        # 학습한다 (80만 스텝 ep_len 10~14 로 확인). 탐색을 넓히려고 초기 std 를
        # 키우면 흔들림 페널티가 커져 이 함정에 바로 빠지고, std 를 줄이면
        # 이번에는 발이 땅에서 안 떨어져 전진을 발견하지 못한다 (2천만 스텝,
        # 명령을 무시하는 상수 정책으로 수렴).
        #
        # 합을 0 에서 자르면 두 국소 최적 사이의 딜레마가 사라진다. 넘어짐은
        # step() 의 FALL_PENALTY 로 따로 처벌하므로 종료 유인은 남지 않는다.
        if C.ONLY_POSITIVE_REWARDS:
            total = max(total, 0.0)
        return total, {k: float(v) for k, v in t.items()}

    def _limit_violation(self) -> float:
        """가동 한계 근처에 들어간 정도 (rad). 여유를 절대 각도로 잡는다."""
        q, m = self.data.qpos[7:], C.LIMIT_MARGIN
        over = np.clip(q - (self.joint_range[:, 1] - m), 0.0, None)
        under = np.clip((self.joint_range[:, 0] + m) - q, 0.0, None)
        return float(np.sum(over + under))

    def _air_time_reward(self) -> float:
        """착지 순간, 공중에 있던 시간이 목표에 가까울수록 보상.

        없으면 발을 끌며 미끄러지는 보행으로 수렴한다. 정지 명령일 때는
        보상하지 않아 제자리 서기를 방해하지 않는다.
        """
        if np.linalg.norm(self._command[:2]) < 0.05:
            return 0.0
        return float(np.sum((self._air_at_contact - C.AIR_TIME_TARGET)
                            * self._first_contact))

    def _terminated(self) -> bool:
        if self.data.qpos[2] < self.target_height * C.FALL_HEIGHT_RATIO:
            return True
        if self._projected_gravity()[2] > C.FALL_TILT:
            return True
        return not np.isfinite(self.data.qpos).all()

    # ------------------------------------------------------------------ 렌더
    def render(self):
        if self._viewer is None:
            import mujoco.viewer
            self._viewer = mujoco.viewer.launch_passive(self.model, self.data)
        if self._viewer.is_running():
            self._viewer.sync()

    def close(self):
        if self._viewer is not None:
            self._viewer.close()
            self._viewer = None
