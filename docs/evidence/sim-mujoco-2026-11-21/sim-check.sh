#!/usr/bin/env bash
# Run as jorah. Installs MuJoCo 3.17.0 (+ Pillow) from PyPI into ~/sandbox/sim-check/venv,
# then renders and simulates. With --offline-only it skips the install.
set -euo pipefail
D=$HOME/sandbox/sim-check; mkdir -p "$D"; cd "$D"
if [ "${1:-}" != --offline-only ]; then
  python3 -m venv --clear venv
  venv/bin/pip install -q --only-binary :all: mujoco==3.17.0 pillow 2>&1 | tail -3
fi
venv/bin/python -c "import mujoco, PIL; print('mujoco', mujoco.__version__)"
/opt/jorah-bench/bin/cad-python "$D/bracket.py" "$D/bracket.stl"
for gl in egl osmesa; do
  echo "--- MUJOCO_GL=$gl"
  if MUJOCO_GL=$gl PYOPENGL_PLATFORM=$gl EGL_PLATFORM=surfaceless venv/bin/python "$D/arm.py" "$D/out-$gl" "$D/bracket.stl" 2>&1 | tail -4; then break; fi
done
ls -la "$D"/out-* 2>/dev/null | cut -c1-90
