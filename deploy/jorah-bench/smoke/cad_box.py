"""STEP export from build123d: a 60 x 40 x 20 mm block with a 10 mm hole, written to argv[1]."""
import sys

from build123d import Box, Cylinder, export_step

out = sys.argv[1]
part = Box(60, 40, 20) - Cylinder(radius=5, height=20)
if not export_step(part, out):
    sys.exit("export_step returned False")
print(f"volume_mm3={part.volume:.1f}")
