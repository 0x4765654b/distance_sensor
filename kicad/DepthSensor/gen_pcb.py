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
import glob
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
PCB = HERE / "DepthSensor.kicad_pcb"
SCH = HERE / "DepthSensor.kicad_sch"
BUILD = HERE / "build"
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
FP_STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
FP_LOCAL = {"SaltMon": str(HERE.parent / "lib" / "SaltMon.pretty")}
JAR = sorted(glob.glob(str(HERE.parent / "freerouting" / "freerouting-*.jar")))[-1]

# ---------------------------------------------------------------- geometry (mm)
X0, Y0 = 100.0, 100.0
W, H = 80.5, 106.0            # MEC-02
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
    "C4": (160.5, 169.5, 0), "C6": (172.0, 170.0, 0),
    "J2": (165.0, 180.5, 90),
    "J4": (178.0, 144.0, 0),
    # test pads down the left edge
    **{f"TP{i + 1}": (103.0, 128.0 + 4.0 * i, 0) for i in range(6)},
    **{k: (x, y, 0) for k, (x, y) in HOLES.items()},
}

# reference-text positions (absolute, horizontal) where the footprint default collides or falls off the board
REF_AT = {"U1": (145.84, 188.0), "J2": (171.8, 180.5), "C6": (178.3, 170.0)}

SOLID_GND_PADS = [("U2", "10")]

POWER_NETS = {"/GND": 0.6, "/V_SYS": 0.6, "/VIN_RAW": 0.8, "/SW_A": 0.8, "/SW_B": 0.8, "/+3V3": 0.4}

mm = pcbnew.FromMM


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def netlist():
    BUILD.mkdir(exist_ok=True)
    xml = BUILD / "carrier.net.xml"
    subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadxml", "-o", str(xml), str(SCH)],
                   check=True, capture_output=True)
    root = ET.parse(xml).getroot()
    comps = {}
    for c in root.iter("comp"):
        fields = {f.get("name"): f.text or "" for f in c.iter("field")}
        comps[c.get("ref")] = {"value": c.findtext("value"), "fp": c.findtext("footprint"),
                               "uuid": c.findtext("tstamps").split()[0],
                               "fields": {k: fields.get(k, "") for k in ("Datasheet", "Description")}}
    pad_net = {}
    for n in root.iter("net"):
        name = n.get("name")
        if name.startswith("unconnected-"):  # pin names inside are escaped; only "/" sheet paths stay literal
            name = name.replace("/", "{slash}")
        for node in n.iter("node"):
            pad_net[(node.get("ref"), node.get("pin"))] = name
    return comps, pad_net


def edge_poly(board, pts):
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(ax, ay))
        s.SetEnd(pt(bx, by))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)


def edge_circle(board, x, y, d):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_CIRCLE)
    s.SetCenter(pt(x, y))
    s.SetEnd(pt(x + d / 2, y))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(mm(0.1))
    board.Add(s)


def outline():
    x1, y1 = X0 + W, Y0 + H
    return [(X0 + NW, Y0), (x1 - NW, Y0), (x1 - NW, Y0 + NH), (x1, Y0 + NH), (x1, y1 - NH), (x1 - NW, y1 - NH),
            (x1 - NW, y1), (X0 + NW, y1), (X0 + NW, y1 - NH), (X0, y1 - NH), (X0, Y0 + NH), (X0 + NW, Y0 + NH)]


def gnd_pour(board, net):
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(net)
        z.SetZoneName(f"GND_{board.GetLayerName(layer)}")
        z.SetLocalClearance(mm(0.4))
        z.SetMinThickness(mm(0.25))
        z.SetThermalReliefGap(mm(0.5))
        z.SetThermalReliefSpokeWidth(mm(0.5))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetAssignedPriority(0)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in outline():
            ol.Append(mm(x), mm(y))
        board.Add(z)
    # pads that tracks crowd to a single thermal spoke (DRC starved_thermal): connect them solid
    for ref, num in SOLID_GND_PADS:
        board.FindFootprintByReference(ref).FindPadByNumber(num).SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def rules(board):
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_MinClearance = mm(0.2)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.5)
    ns = ds.m_NetSettings
    dflt = ns.GetDefaultNetclass()
    dflt.SetTrackWidth(mm(0.3))
    dflt.SetClearance(mm(0.25))
    dflt.SetViaDiameter(mm(0.8))
    dflt.SetViaDrill(mm(0.4))
    for width in sorted(set(POWER_NETS.values())):
        name = f"Power_{str(width).replace('.', 'p')}"
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(width))
        nc.SetClearance(mm(0.3))
        nc.SetViaDiameter(mm(1.0))
        nc.SetViaDrill(mm(0.5))
        ns.SetNetclass(name, nc)
    for net, width in POWER_NETS.items():
        ns.SetNetclassPatternAssignment(net, f"Power_{str(width).replace('.', 'p')}")


STRIP = {"footprint", "segment", "via", "arc", "zone", "gr_line", "gr_rect", "gr_circle", "gr_arc", "gr_poly",
         "gr_text", "gr_text_box", "dimension", "group", "generated", "image", "table", "target", "net"}


def strip_board():
    """Drop all items from the board file, keeping header/setup/layers. Done as text because
    BOARD.Remove() on footprints corrupts the SWIG type table (later loads return raw pointers)."""
    text = PCB.read_text()
    BUILD.mkdir(exist_ok=True)
    (BUILD / "DepthSensor.kicad_pcb.bak").write_text(text)
    out, i, depth, start = [], 0, 0, None
    keep_from = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            depth += 1
            if depth == 2:
                start = i
        elif c == ")":
            if depth == 2:
                head = text[start + 1:i + 1].split(None, 1)[0].rstrip(")")
                if head in STRIP:
                    out.append(text[keep_from:start])
                    keep_from = i + 1
            depth -= 1
        i += 1
    out.append(text[keep_from:])
    PCB.write_text("".join(out))


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
    comps, pad_net = netlist()
    strip_board()
    board = pcbnew.LoadBoard(str(PCB))

    # outline, antenna slot, cable-tie holes
    edge_poly(board, outline())
    sx0, sy0, sx1, sy1 = SLOT
    edge_poly(board, [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)])
    for x, y in TIE_HOLES:
        edge_circle(board, x, y, 3.0)

    # nets
    nets = {}
    for name in sorted(set(pad_net.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    # footprints
    io = pcbnew.PCB_IO_KICAD_SEXPR()  # pcbnew.FootprintLoad breaks once a board is loaded
    missing = set(comps) - set(PLACE)
    assert not missing, f"no placement for {sorted(missing)}"
    for ref, c in comps.items():
        lib, name = c["fp"].split(":")
        fp = io.FootprintLoad(FP_LOCAL.get(lib, f"{FP_STOCK}/{lib}.pretty"), name)
        assert fp, c["fp"]
        fp.SetFPIDAsString(c["fp"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        for k, v in c["fields"].items():
            fp.SetField(k, v)
        fp.SetPath(pcbnew.KIID_PATH(f"/{c['uuid']}"))
        x, y, rot = PLACE[ref]
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        board.Add(fp)
        tidy_silk(fp, ref)
        for pad in fp.Pads():
            net = pad_net.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])

    t = pcbnew.PCB_TEXT(board)
    t.SetText("SaltMon carrier v0.1")
    t.SetPosition(pt(118.0, 150.0))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
    board.Add(t)

    rules(board)
    return board


def route(board):
    dsn, ses = BUILD / "carrier.dsn", BUILD / "carrier.ses"
    assert pcbnew.ExportSpecctraDSN(board, str(dsn)), "DSN export failed"
    subprocess.run(["java", "-jar", JAR, "-de", str(dsn), "-do", str(ses), "-mp", "100",
                    "--gui.enabled=false"], check=True)
    assert pcbnew.ImportSpecctraSES(board, str(ses)), "SES import failed"


if __name__ == "__main__":
    board = build()
    if "--no-route" not in sys.argv:
        route(board)
        gnd_pour(board, board.FindNet("/GND"))
    board.Save(str(PCB))
    print("wrote", PCB)
