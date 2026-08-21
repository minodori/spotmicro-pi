# SpotMicro — 로봇 없이 확인할 수 있는 것들
#
#   make setup    처음 한 번
#   make verify   모델이 실물과 맞는지 8단계 검증   <- 로봇 불필요
#   make eval     학습된 정책을 재생                <- 로봇 불필요
#
# 로봇이 필요한 것은 JetsonNano/ 아래에 있습니다.

.DEFAULT_GOAL := help
.PHONY: help setup verify model eval eval-render train gait clean

help:
	@echo ''
	@echo '  로봇 없이 되는 것'
	@echo '    make setup        의존성 설치 (Python 3.12, GPU 불필요)'
	@echo '    make verify       모델-실물 일치 8단계 검증. 기하는 0.0000mm 를 요구'
	@echo '    make model        실측 상수에서 시뮬레이션 모델을 다시 생성'
	@echo '    make eval         배포된 정책을 재생하고 실물 이식 가능성을 판정'
	@echo '    make eval-render  같은 것을 화면으로'
	@echo '    make gait         규칙 기반 보행을 영상으로 저장'
	@echo '    make train        직접 학습 (CPU, 수 시간)'
	@echo ''
	@echo '  치수를 바꿨다면 make model 다음에 make verify 입니다.'
	@echo '  자세한 것은 CONTRIBUTING.md 를 보세요.'
	@echo ''

setup:
	uv sync

# 시뮬레이션 모델은 손으로 쓰는 파일이 아니라 실측 상수에서 나온 생성물이다.
# 정본은 Kinematics/kinematics.py 한 곳뿐이다.
model:
	uv run python rl/gen_mjcf.py

# 게이트 3(순기구학 대조)이 핵심이다. 시뮬레이션과 실물 제어가 같은 기하·같은
# 부호규약을 쓴다는 것을 증명하므로, 통과해야 정책을 실물에 올릴 수 있다.
verify: model
	uv run python rl/validate_mjcf.py

eval:
	uv run python -m rl.eval --run checkpoints --command 0.2 0 0

eval-render:
	uv run python -m rl.eval --run checkpoints --command 0.2 0 0 --render --episodes 1

gait:
	uv run python rl/render_gait.py

train:
	OMP_NUM_THREADS=1 uv run python -m rl.train --obs A --timesteps 20000000

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
