"""Writes the KiCad smoke test's board with KiCad's own pcbnew module (python3, the PPA's KiCad),
so the file is in the installed KiCad's format: a 30 x 20 mm outline, two 0603 resistors and a track.
Usage: python3 make_board.py OUT.kicad_pcb (run once by hand; the result is board.kicad_pcb here)."""
import sys

import pcbnew

board = pcbnew.BOARD()
mm = pcbnew.FromMM
outline = pcbnew.PCB_SHAPE(board)
outline.SetShape(pcbnew.SHAPE_T_RECT)
outline.SetStart(pcbnew.VECTOR2I(mm(0), mm(0)))
outline.SetEnd(pcbnew.VECTOR2I(mm(30), mm(20)))
outline.SetLayer(pcbnew.Edge_Cuts)
outline.SetWidth(mm(0.1))
board.Add(outline)
net = pcbnew.NETINFO_ITEM(board, "SIG")
board.Add(net)
lib = "/usr/share/kicad/footprints/Resistor_SMD.pretty"
pads = []
for ref, x in (("R1", 10), ("R2", 20)):
    fp = pcbnew.FootprintLoad(lib, "R_0603_1608Metric")
    fp.SetReference(ref)
    fp.SetValue("10k")
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(10)))
    board.Add(fp)
    pads.append(fp.FindPadByNumber("2" if ref == "R1" else "1"))
for pad in pads:
    pad.SetNet(net)
track = pcbnew.PCB_TRACK(board)
track.SetStart(pads[0].GetPosition())
track.SetEnd(pads[1].GetPosition())
track.SetWidth(mm(0.25))
track.SetLayer(pcbnew.F_Cu)
track.SetNet(net)
board.Add(track)
pcbnew.SaveBoard(sys.argv[1], board)
print("wrote", sys.argv[1])
