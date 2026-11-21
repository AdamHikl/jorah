# A servo bracket in build123d, exported as STL (mm) for the sim check.
import sys
from build123d import Box, Cylinder, Pos, export_stl
plate = Box(40, 30, 3)
wall = Pos(-18.5, 0, 11.5) * Box(3, 30, 20)
hole = Pos(-18.5, 0, 14) * Cylinder(4, 10, rotation=(0, 90, 0))
part = plate + wall - hole - Pos(8, 0, 0) * Cylinder(1.6, 5)
export_stl(part, sys.argv[1])
print("bracket volume mm3:", round(part.volume, 1))
