import torch
import os
from isaacsim import SimulationApp

app = SimulationApp({
    "headless": False,
    "extra_args": ["--enable", "isaacsim.asset.importer.urdf"]
})

from omni.isaac.core import World
from omni.isaac.core.utils.stage import add_reference_to_stage
import omni.kit.commands
from isaacsim.asset.importer.urdf import _urdf

urdf_path = os.path.abspath(r"urdf\spotmicroai_gen.urdf.xml").replace("\\", "/")
print(f"URDF 경로: {urdf_path}")

result, import_config = omni.kit.commands.execute("URDFCreateImportConfig")
import_config.merge_fixed_joints = False
import_config.fix_base = False
import_config.make_default_prim = True
import_config.self_collision = False
import_config.default_drive_type = _urdf.UrdfJointTargetType.JOINT_DRIVE_POSITION

result, prim_path = omni.kit.commands.execute(
    "URDFParseAndImportFile",
    urdf_path=urdf_path,
    import_config=import_config,
)

print(f"임포트 결과: {result}")
print(f"prim_path: {prim_path}")

world = World()
world.scene.add_default_ground_plane()
world.reset()

print("실행 중... (창 닫으면 종료)")

while app.is_running():
    world.step(render=True)

app.close()
