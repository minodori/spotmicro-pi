import torch  # Isaac Sim 시작 전에 DLL 먼저 로드

from isaacsim import SimulationApp

app = SimulationApp({"headless": False})

from omni.isaac.core import World

world = World()
world.reset()

print("Isaac Sim 실행 중...")

while app.is_running():
    world.step(render=True)

app.close()
