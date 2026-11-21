# Sim check: a 3-joint servo arm with a wrist camera in MuJoCo, rendered headless on the CPU,
# plus multi-view pictures of a build123d part. Writes PNGs and a JSON summary to argv[1].
import json, os, sys, time
out = sys.argv[1]
stl = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(out, exist_ok=True)
import mujoco
import numpy as np
from PIL import Image

MESH = f'<mesh name="bracket" file="{stl}" scale="0.001 0.001 0.001"/>' if stl else ""
BRACKET = '<geom type="mesh" mesh="bracket" pos="0.25 0.15 0" rgba="0.3 0.6 0.9 1"/>' if stl else ""
XML = f"""
<mujoco model="servo_arm">
  <compiler angle="radian"/>
  <option timestep="0.002" gravity="0 0 -9.81"/>
  <asset>{MESH}<texture name="grid" type="2d" builtin="checker" rgb1=".85 .85 .85" rgb2=".7 .7 .7" width="256" height="256"/>
    <material name="floor" texture="grid" texrepeat="8 8"/></asset>
  <worldbody>
    <light pos="0 0 1.5" dir="0 0 -1"/>
    <geom type="plane" size="1 1 0.01" material="floor"/>
    <geom name="target" type="box" size="0.02 0.02 0.02" pos="0.22 0.0 0.02" rgba="0.9 0.1 0.1 1"/>
    {BRACKET}
    <camera name="scene" pos="0.6 -0.6 0.5" xyaxes="0.707 0.707 0 -0.35 0.35 0.87"/>
    <body name="base" pos="0 0 0.05">
      <geom type="cylinder" size="0.05 0.05" rgba="0.2 0.2 0.2 1" mass="0.5"/>
      <joint name="yaw" type="hinge" axis="0 0 1" range="-3.14 3.14"/>
      <body name="upper" pos="0 0 0.06">
        <joint name="shoulder" type="hinge" axis="0 1 0" range="-1.6 1.6"/>
        <geom type="capsule" fromto="0 0 0 0 0 0.15" size="0.015" rgba="0.9 0.6 0.1 1" mass="0.12"/>
        <body name="fore" pos="0 0 0.15">
          <joint name="elbow" type="hinge" axis="0 1 0" range="-2.4 2.4"/>
          <geom type="capsule" fromto="0 0 0 0.14 0 0" size="0.012" rgba="0.9 0.6 0.1 1" mass="0.08"/>
          <body name="wrist" pos="0.14 0 0">
            <geom type="box" size="0.015 0.015 0.01" rgba="0.1 0.1 0.1 1" mass="0.03"/>
            <camera name="wrist_cam" pos="0.02 0 0" xyaxes="0 -1 0 0 0 1" fovy="60"/>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <!-- hobby servos: position control, about 1.5 N*m stall torque -->
    <position joint="yaw" kp="8" forcerange="-1.5 1.5"/>
    <position joint="shoulder" kp="8" forcerange="-1.5 1.5"/>
    <position joint="elbow" kp="8" forcerange="-1.5 1.5"/>
  </actuator>
</mujoco>"""
m = mujoco.MjModel.from_xml_string(XML)
d = mujoco.MjData(m)
target = np.array([0.0, 0.9, 0.6])  # yaw, shoulder, elbow (rad)
d.ctrl[:] = target
t0 = time.time()
for _ in range(1500):  # 3 simulated seconds
    mujoco.mj_step(m, d)
sim_s = time.time() - t0
summary = {"mujoco": mujoco.__version__, "gl": os.environ.get("MUJOCO_GL"), "target_rad": target.tolist(),
           "reached_rad": [round(float(x), 3) for x in d.qpos[:3]], "actuator_torque_Nm": [round(float(x), 3) for x in d.actuator_force[:3]],
           "wall_s_for_3_sim_s": round(sim_s, 3), "wrist_xyz_m": [round(float(x), 3) for x in d.body("wrist").xpos]}
r = mujoco.Renderer(m, height=480, width=640)
for cam in ("scene", "wrist_cam"):
    t0 = time.time(); r.update_scene(d, camera=cam); img = r.render()
    Image.fromarray(img).save(f"{out}/{cam}.png")
    summary[f"{cam}_render_s"] = round(time.time() - t0, 3)
    summary[f"{cam}_mean_pixel"] = round(float(img.mean()), 1)
# free cameras around the part, like CAD screenshots
if stl:
    cam = mujoco.MjvCamera(); cam.lookat[:] = [0.25, 0.15, 0.02]; cam.distance = 0.25
    for name, az, el in (("part_front", 90, 0), ("part_side", 0, 0), ("part_top", 90, -89), ("part_iso", 45, -30)):
        cam.azimuth, cam.elevation = az, el
        r.update_scene(d, camera=cam); Image.fromarray(r.render()).save(f"{out}/{name}.png")
json.dump(summary, open(f"{out}/summary.json", "w"), indent=1)
print(json.dumps(summary))
