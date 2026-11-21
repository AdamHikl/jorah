# MuJoCo pictures and physics in the project-run sandbox, 2026-11-21

Question: can a project run see a design and simulate an arm's joints and camera without a GPU,
Fusion or a display? Asked after Adam chose open Linux tools over a Fusion MCP bridge.

**Ran:** `sim-check.sh` on the PC as `jorah`, twice: once directly, then inside Claude Code's
sandbox with the project-run settings (`claude -p`, Opus 5.5, the bench's `env.sh`, as
`scripts/pc/bench-smoke.sh --via-claude` does). Inside the sandbox it installed MuJoCo 3.17.0 and
Pillow from PyPI into `~/sandbox/sim-check/venv`, exported `bracket.py`'s part with `cad-python`, and
ran `arm.py` with `MUJOCO_GL=egl`.

**Result [measured, inside the sandbox]:**

| What | Value |
|---|---|
| MuJoCo | 3.17.0 (4.x has no wheel for Python 3.12) |
| Renderer | EGL on Mesa's CPU renderer; no GPU, no display |
| 3 simulated seconds, 3 joints | 0.003 s wall time |
| 640x480 scene picture | 0.27 s (first render); wrist camera 0.014 s |
| Servo target (rad) | yaw 0, shoulder 0.9, elbow 0.6 |
| Reached (rad) | yaw 0, shoulder 1.122, elbow 0.357 |
| Servo torque | shoulder -1.5 and elbow 1.5 N*m: both at the 1.5 N*m limit |

The arm didn't reach its target: the forearm ends on the floor (wrist at 3.5 cm height, `scene.png`)
and both servos stall at their limit. That is the kind of finding a run can now make before Adam
builds anything. The wrist camera's picture (`wrist_cam.png`) shows the floor from close up for
the same reason. `part_*.png` are four views of the build123d bracket, like CAD screenshots.

Outside the sandbox the same script gave the same numbers. An `EGLError` traceback at interpreter
exit comes from MuJoCo freeing its EGL context and doesn't affect the output.

**Not checked:** FEA (needs FreeCAD from the toolbox), long simulations, memory with the voice
models busy, and MuJoCo's own camera calibration against a real Pi camera.
