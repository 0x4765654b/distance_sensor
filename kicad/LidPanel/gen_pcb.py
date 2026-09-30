#!/usr/bin/env python3
"""Build the SaltMon lid panel PCB and the 1:1 lid drilling template, then autoroute with Freerouting.

Must run under KiCad's bundled Python (it needs `pcbnew`):
  KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
  $KPY kicad/LidPanel/gen_pcb.py            # place + route + pour
  $KPY kicad/LidPanel/gen_pcb.py --no-route # place only

Geometry: docs/requirements.md §5.3 and MEC-06, MEC-09. Board coords are the lid seen from OUTSIDE (the board's
front faces the lid, so the KiCad front view is what you see on the wall): (X0, Y0) = inside top-left corner of
the lid, +Y down toward the bottom wall. The drilling template is drawn on User.Drawings; print it with
  kicad-cli pcb export pdf --mode-single -l User.Drawings --scale 1 -o lid-template.pdf LidPanel.kicad_pcb
"""
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
from pcbgen import (add_footprints, add_nets, add_text, edge_circle, edge_poly, gnd_pour, mm, netlist, pt,  # noqa: E402
                    route, rules, strip_board)

PCB = HERE / "LidPanel.kicad_pcb"
SCH = HERE / "LidPanel.kicad_sch"
BUILD = HERE / "build"

# ---------------------------------------------------------------- geometry (mm)
X0, Y0 = 100.0, 50.0          # lid inside top-left
LID_IN = (82.6, 108.0)        # inside W x L (§9)
WALL = 3.15                   # (outside − inside) / 2
PILLAR = (19.1, 12.7)         # corner pillars: across the width x along the length
BOARD = (116.3, 64.0, 166.3, 127.0)   # x0, y0, x1, y1: 50 x 63, centered across the lid, clear of the pillars
HOLES = {"H1": (119.8, 67.5), "H2": (162.8, 67.5), "H3": (119.8, 123.5), "H4": (162.8, 123.5)}

COL_L, COL_R = X0 + 26.3, X0 + 56.3         # LED columns, 30 mm apart
ROWS = [Y0 + 35.0, Y0 + 46.0, Y0 + 57.0, Y0 + 68.0]
LED_HOLE = 5.0                              # flat-top body through the lid; the 5.8 mm flange stops inside
SW1_AT = (X0 + 30.0, Y0 + 88.0)             # panel slide switch (slot + screws: measure the part)
SW2_AT = (X0 + 52.0, Y0 + 88.0)             # panel push-button (hole = its bushing diameter)

# LED ref -> (column x, row index, lid label); the 2-pin footprint's pad 1 (K) is 1.27 left of the body center,
# the 3-pin one's pad 1 is 2.54 left
LEDS = {"D1": (COL_L, 0, "FULL"), "D2": (COL_L, 1, "MID"), "D3": (COL_L, 2, "LOW"), "D4": (COL_L, 3, "REFILL"),
        "D8": (COL_R, 0, "PWR"), "D7": (COL_R, 1, "NET"), "D5": (COL_R, 2, "DATA"), "D6": (COL_R, 3, "SENS")}

# ---------------------------------------------------------------- placement: ref -> (x, y, rotation°[, "back"])
PLACE = {
    **{r: (x - (2.54 if r == "D7" else 1.27), ROWS[i], 0) for r, (x, i, _) in LEDS.items()},
    # right-angle header on the back, ribbon leaving toward the top wall (the carrier's J_PANEL is top-left)
    "J1": (150.19, 79.0, 90, "back"),
    "J2": (128.0, 123.5, 0),
    "J3": (150.0, 123.5, 0),
    **{k: (x, y, 0) for k, (x, y) in HOLES.items()},
}

POWER_NETS = {"/GND": 0.6, "/SW_A": 0.8, "/SW_B": 0.8}


def outline():
    x0, y0, x1, y1 = BOARD
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def tidy_silk(fp, ref):
    if ref.startswith("H"):
        fp.Reference().SetVisible(False)
    if ref in LEDS or ref in ("J2", "J3"):  # LED refs on the inner side of the body, pad refs above the pads
        x, i, _ = LEDS.get(ref, (None, None, None))
        pads = list(fp.Pads())
        c = (pads[0].GetPosition() + pads[-1].GetPosition()) / 2
        dx, dy = (5.2 if x == COL_L else -5.2, 0) if ref in LEDS else (0, -2.6)
        fp.Reference().SetPosition(pcbnew.VECTOR2I(int(c.x) + mm(dx), int(c.y) + mm(dy)))
        fp.Reference().SetTextAngleDegrees(0)


def template(board):
    """1:1 lid drilling template on User.Drawings: lid outside and inside edges, pillars, the lid board outline,
    and every hole with its label."""
    L = pcbnew.Dwgs_User
    w, h = LID_IN
    edge_poly(board, [(X0 - WALL, Y0 - WALL), (X0 + w + WALL, Y0 - WALL), (X0 + w + WALL, Y0 + h + WALL),
                      (X0 - WALL, Y0 + h + WALL)], L, 0.2)
    edge_poly(board, [(X0, Y0), (X0 + w, Y0), (X0 + w, Y0 + h), (X0, Y0 + h)], L, 0.1)
    pw, pl = PILLAR
    for cx, cy, sx, sy in [(X0, Y0, 1, 1), (X0 + w, Y0, -1, 1), (X0, Y0 + h, 1, -1), (X0 + w, Y0 + h, -1, -1)]:
        edge_poly(board, [(cx, cy), (cx + sx * pw, cy), (cx + sx * pw, cy + sy * pl), (cx, cy + sy * pl)], L, 0.1)
    edge_poly(board, outline(), L, 0.1)

    def cross(x, y, r=4.0):
        edge_poly(board, [(x - r, y), (x + r, y)], L, 0.1)
        edge_poly(board, [(x, y - r), (x, y + r)], L, 0.1)

    def note(s, x, y, size=1.5):  # multi-line block hanging down from (x, y)
        add_text(board, s, x, y, size, L).SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_TOP)

    for ref, (x, i, label) in LEDS.items():
        y = ROWS[i]
        edge_circle(board, x, y, LED_HOLE, L, 0.15)
        cross(x, y)
        # labels on the outer side of each column: the 30 mm between the columns is too narrow for two
        add_text(board, f"{label}  Ø{LED_HOLE:g}", x + (-5.0 if x == COL_L else 5.0), y, 1.5, L) \
            .SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if x == COL_L else pcbnew.GR_TEXT_H_ALIGN_LEFT)
    cross(*SW1_AT, 6.0)
    note("SW1 switch\nslot per part", SW1_AT[0], SW1_AT[1] + 10.0, 1.2)
    cross(*SW2_AT, 6.0)
    for d in (7.0, 12.0, 16.0):
        edge_circle(board, *SW2_AT, d, L, 0.1)
    note("SW2 button\nØ per bushing\n(7 / 12 / 16 shown)", SW2_AT[0], SW2_AT[1] + 10.0, 1.2)
    for x, y in HOLES.values():
        edge_circle(board, x, y, 3.2, L, 0.1)
        cross(x, y, 2.5)
    note("SaltMon lid drilling template, 1:1\nView: OUTSIDE of the lid, bottom wall down\n"
         "Check the 50 mm bar before drilling\nSmall circles: lid-board M3 screws (MEC-09)",
         X0 + w / 2, Y0 + h + WALL + 4.0)
    by = Y0 + h + WALL + 17.0
    edge_poly(board, [(X0 + w / 2 - 25, by), (X0 + w / 2 + 25, by)], L, 0.3)
    add_text(board, "50 mm", X0 + w / 2, by + 2.5, 1.5, L)


def build():
    comps, pad_net = netlist(SCH, BUILD)
    strip_board(PCB, BUILD)
    board = pcbnew.LoadBoard(str(PCB))
    edge_poly(board, outline())
    nets = add_nets(board, pad_net)
    add_footprints(board, comps, pad_net, nets, PLACE, tidy_silk)
    for ref, (x, i, label) in LEDS.items():
        add_text(board, label, x, ROWS[i] - 4.6, 1.0)
    add_text(board, "SaltMon lid panel v0.1", 141.3, 88.5, 1.2)
    add_text(board, "LEDs + flanges face the lid", 141.3, 112.0, 1.0)
    template(board)
    rules(board, POWER_NETS)
    return board


if __name__ == "__main__":
    board = build()
    if "--no-route" not in sys.argv:
        route(board, BUILD)
        gnd_pour(board, board.FindNet("/GND"), outline())
    board.Save(str(PCB))
    print("wrote", PCB)
