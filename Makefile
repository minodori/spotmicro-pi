# SpotMicro — 로봇 없이 확인할 수 있는 것들
#
#   make setup    처음 한 번
#   make verify   모델이 실물과 맞는지 8단계 검증   <- 로봇 불필요
#   make eval     학습된 정책을 재생                <- 로봇 불필요
#
# 로봇이 필요한 것은 RaspberryPi/ 아래에 있습니다.

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
	@echo '    make gait-check   실물에서 걷는 궤적을 시뮬에서 재생해 속도를 잰다'
	@echo '    make gait         같은 것을 영상으로 저장'
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

# 명령 0.3 을 쓴다. 배포된 정책은 명령 범위의 위쪽에서만 추종하기 때문이다
# (checkpoints/README.md 참조). 낮은 명령을 주면 제자리에 선다 — 고장이 아니다.
eval:
	uv run python -m rl.eval --run checkpoints --command 0.3 0 0 --no-domain-rand

eval-render:
	uv run python -m rl.eval --run checkpoints --command 0.3 0 0 --no-domain-rand --render --episodes 1

# 게이트 3(순기구학 대조)은 기하가 같다는 것만 증명한다. 질량·관성·마찰·서보
# 게인이 실물과 맞는지는 말해주지 않는다. 그것을 보는 방법은 **실물에서 이미
# 걷는 것으로 확인된 궤적**을 시뮬레이터에 그대로 넣고 같은 속도가 나오는지
# 재는 것이다. 실물 실측 49~50mm/s, 시뮬 52mm/s.
gait-check:
	uv run python -m rl.render_gait --measure

gait:
	uv run python -m rl.render_gait

train:
	OMP_NUM_THREADS=1 uv run python -m rl.train --obs A --timesteps 20000000

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
