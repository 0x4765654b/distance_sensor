#!/usr/bin/env python3
"""Build the SaltMon carrier PCB: outline, placement, rules, then autoroute with Freerouting.

Must run under KiCad's bundled Python (it needs `pcbnew`):
  KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
  $KPY kicad/DepthSensor/gen_pcb.py            # place + route + pour
  $KPY kicad/DepthSensor/gen_pcb.py --no-route # place only (inspect before routing)

Inputs: DepthSensor.kicad_sch (via kicad-cli netlist export), kicad/freerouting/freerouting-*.jar
(not in git: download from https://github.com/freerouting/freerouting/releases, tested with 2.4.1; needs Java 21+).
Geometry: docs/requirements.md §9 (MEC-02…MEC-08). Board coords: origin at (100, 100) = top-left of the
board bounding box, portrait, +Y down toward the bottom wall (USB-C cut-out + DC jack).
"""
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
from pcbgen import (add_footprints, add_nets, add_tracks, edge_circle, edge_poly, gnd_pour, mm, netlist, pt,  # noqa: E402
                    route, rules, strip_board)

PCB = HERE / "DepthSensor.kicad_pcb"
SCH = HERE / "DepthSensor.kicad_sch"
BUILD = HERE / "build"

# ---------------------------------------------------------------- geometry (mm)
X0, Y0 = 100.0, 100.0
W, H = 80.5, 106.0            # MEC-02 bounding box of the old two-tab outline; the top edge is now at Y0 + NH
NW, NH = 20.5, 14.0           # corner notches (across width x along length)
SLOT = (133.5, 143.0, 158.2, 157.2)       # antenna slot under the kit overhang (x0, y0, x1, y1)
TIE_HOLES = [(163.0, 187.5), (169.0, 187.5)]  # sensor-ribbon cable tie, Ø3
HOLES = {"H1": (104.0, 118.0), "H2": (177.0, 118.0), "H3": (104.0, 188.0), "H4": (176.5, 188.0)}

# ---------------------------------------------------------------- placement: ref -> (x, y, rotation°)
PLACE = {
    # bottom tab: DC jack (front flush with bottom edge) + kit (USB end flush, antenna up)
    "J1": (125.84, 192.3, 0),
    "U1": (134.41, 159.315, 0),
    # top: lid-panel header, LED driver, pull-downs, LED resistors
    "J3": (122.0, 122.5, 90),
    "U2": (152.0, 116.5, 0),
    "C2": (143.5, 137.0, 0),
    "RN1": (120.0, 130.5, 0),
    **{f"R{i + 1}": (162.5, 123.0 + 3.2 * i, 0) for i in range(8)},
    "R9": (110.0, 138.0, 0),
    # left: power path
    "F1": (112.0, 186.0, 0),
    "D1": (123.0, 177.0, 180),
    "C1": (113.0, 166.0, 0),
    "D2": (104.0, 158.0, 0),
    "C3": (122.0, 168.0, 0),
    # right: sensor interface, button, spare
    "R10": (160.5, 158.5, 0), "C5": (173.2, 158.5, 0),
    "R11": (160.5, 162.0, 0), "C7": (173.2, 162.0, 0),
    "R12": (160.5, 165.5, 0), "C8": (173.2, 165.5, 0),
    "C4": (160.5, 170.0, 0), "C6": (172.0, 170.0, 0),
    "J2": (165.0, 180.5, 90),
    "J4": (178.0, 144.5, 0),
    # test pads down the left edge
    **{f"TP{i + 1}": (103.0, 128.0 + 4.0 * i, 0) for i in range(6)},
    **{k: (x, y, 0) for k, (x, y) in HOLES.items()},
}

# reference-text positions (absolute, horizontal) where the footprint default collides or falls off the board
REF_AT = {"U1": (145.84, 188.0), "U2": (155.81, 126.66), "J2": (171.8, 180.5), "C6": (178.3, 170.0)}

SOLID_GND_PADS = [("U2", "10")]

# hand-placed track stubs (net, layer, width, points): Freerouting can't escape U1 pad 1 (+3V3) from under the
# antenna slot on its own, so lead it out to the open area on the left first
PREROUTE = [("/+3V3", "B.Cu", 0.4, [(134.41, 159.315), (130.5, 159.315), (130.5, 150.0)])]

POWER_NETS = {"/GND": 0.6, "/V_SYS": 0.6, "/VIN_RAW": 0.8, "/SW_A": 0.8, "/SW_B": 0.8, "/+3V3": 0.4}

def outline():
    """Full-width body with only the bottom tab (kit USB end + DC jack reach the bottom wall). The top edge is
    straight at Y0 + NH: the old top tab held no parts."""
    x1, y1 = X0 + W, Y0 + H
    return [(X0, Y0 + NH), (x1, Y0 + NH), (x1, y1 - NH), (x1 - NW, y1 - NH),
            (x1 - NW, y1), (X0 + NW, y1), (X0 + NW, y1 - NH), (X0, y1 - NH)]


def tidy_silk(fp, ref):
    """Keep silkscreen on the board: ref text inside axial/disc bodies (stacked parts), no mounting-hole refs,
    and clip the DC jack's outline at the bottom edge it sits flush against."""
    name = fp.GetFPIDAsString()
    if "R_Axial" in name or "C_Disc" in name:
        pads = list(fp.Pads())
        mid = (pads[0].GetPosition() + pads[1].GetPosition()) / 2
        r = fp.Reference()
        r.SetPosition(pcbnew.VECTOR2I(int(mid.x), int(mid.y)))
        r.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
        r.SetTextThickness(mm(0.15))
        r.SetTextAngleDegrees(0)
    if ref.startswith("H"):
        fp.Reference().SetVisible(False)
    if ref in REF_AT:
        fp.Reference().SetPosition(pt(*REF_AT[ref]))
        fp.Reference().SetTextAngleDegrees(0)
    ymax = mm(Y0 + H - 0.5)
    for it in list(fp.GraphicalItems()):
        if it.GetLayer() != pcbnew.F_SilkS or it.GetClass() != "PCB_SHAPE" or it.GetShape() != pcbnew.SHAPE_T_SEGMENT:
            continue
        a, b = it.GetStart(), it.GetEnd()
        if a.y > ymax and b.y > ymax:
            fp.Remove(it)
        elif a.y > ymax:
            it.SetStart(pcbnew.VECTOR2I(a.x, ymax))
        elif b.y > ymax:
            it.SetEnd(pcbnew.VECTOR2I(b.x, ymax))


def build():
    comps, pad_net = netlist(SCH, BUILD)
    strip_board(PCB, BUILD)
    board = pcbnew.LoadBoard(str(PCB))

    # outline, antenna slot, cable-tie holes
    edge_poly(board, outline())
    sx0, sy0, sx1, sy1 = SLOT
    edge_poly(board, [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)])
    for x, y in TIE_HOLES:
        edge_circle(board, x, y, 3.0)

    nets = add_nets(board, pad_net)
    add_footprints(board, comps, pad_net, nets, PLACE, tidy_silk)

    t = pcbnew.PCB_TEXT(board)
    t.SetText("SaltMon carrier v0.2")
    t.SetPosition(pt(118.0, 150.0))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
    board.Add(t)

    add_tracks(board, nets, PREROUTE)
    rules(board, POWER_NETS)
    return board


if __name__ == "__main__":
    board = build()
    if "--no-route" not in sys.argv:
        route(board, BUILD)
        gnd_pour(board, board.FindNet("/GND"), outline(), SOLID_GND_PADS)
    board.Save(str(PCB))
    print("wrote", PCB)
