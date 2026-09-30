"""Shared helpers for the PCB generators (carrier and lid panel): netlist import, outline, footprints, rules,
Freerouting, GND pour. Must run under KiCad's bundled Python (it needs `pcbnew`)."""
import glob
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
FP_STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
FP_LOCAL = {"SaltMon": str(Path(__file__).resolve().parent / "SaltMon.pretty")}
JAR = sorted(glob.glob(str(Path(__file__).resolve().parent.parent / "freerouting" / "freerouting-*.jar")))[-1]

mm = pcbnew.FromMM


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def netlist(sch, build):
    build.mkdir(exist_ok=True)
    xml = build / "netlist.xml"
    subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadxml", "-o", str(xml), str(sch)],
                   check=True, capture_output=True)
    root = ET.parse(xml).getroot()
    comps = {}
    for c in root.iter("comp"):
        fields = {f.get("name"): f.text or "" for f in c.iter("field")}
        comps[c.get("ref")] = {"value": c.findtext("value"), "fp": c.findtext("footprint"),
                               "uuid": c.findtext("tstamps").split()[0],
                               "fields": {k: v for k, v in fields.items() if k not in ("Reference", "Value", "Footprint")}}
    pad_net = {}
    for n in root.iter("net"):
        name = n.get("name")
        if name.startswith("unconnected-"):  # pin names inside are escaped; only "/" sheet paths stay literal
            name = name.replace("/", "{slash}")
        for node in n.iter("node"):
            pad_net[(node.get("ref"), node.get("pin"))] = name
    return comps, pad_net


def edge_poly(board, pts, layer=pcbnew.Edge_Cuts, width=0.1):
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(ax, ay))
        s.SetEnd(pt(bx, by))
        s.SetLayer(layer)
        s.SetWidth(mm(width))
        board.Add(s)


def edge_circle(board, x, y, d, layer=pcbnew.Edge_Cuts, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_CIRCLE)
    s.SetCenter(pt(x, y))
    s.SetEnd(pt(x + d / 2, y))
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    board.Add(s)


def add_text(board, s, x, y, size=1.2, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    board.Add(t)
    return t


def gnd_pour(board, net, outline, solid_pads=()):
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
        for x, y in outline:
            ol.Append(mm(x), mm(y))
        board.Add(z)
    # pads that tracks crowd to a single thermal spoke (DRC starved_thermal): connect them solid
    for ref, num in solid_pads:
        board.FindFootprintByReference(ref).FindPadByNumber(num).SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def rules(board, power_nets):
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
    for width in sorted(set(power_nets.values())):
        name = f"Power_{str(width).replace('.', 'p')}"
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(width))
        nc.SetClearance(mm(0.3))
        nc.SetViaDiameter(mm(1.0))
        nc.SetViaDrill(mm(0.5))
        ns.SetNetclass(name, nc)
    for net, width in power_nets.items():
        ns.SetNetclassPatternAssignment(net, f"Power_{str(width).replace('.', 'p')}")


STRIP = {"footprint", "segment", "via", "arc", "zone", "gr_line", "gr_rect", "gr_circle", "gr_arc", "gr_poly",
         "gr_text", "gr_text_box", "dimension", "group", "generated", "image", "table", "target", "net"}


def strip_board(pcb, build):
    """Drop all items from the board file, keeping header/setup/layers. Done as text because
    BOARD.Remove() on footprints corrupts the SWIG type table (later loads return raw pointers)."""
    text = pcb.read_text()
    build.mkdir(exist_ok=True)
    (build / f"{pcb.name}.bak").write_text(text)
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
    pcb.write_text("".join(out))


def add_nets(board, pad_net):
    nets = {}
    for name in sorted(set(pad_net.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    return nets


def add_footprints(board, comps, pad_net, nets, place, tidy=None):
    """place: ref -> (x, y, rotation°) or (x, y, rotation°, "back"). tidy(fp, ref) runs after each is added."""
    io = pcbnew.PCB_IO_KICAD_SEXPR()  # pcbnew.FootprintLoad breaks once a board is loaded
    missing = set(comps) - set(place)
    assert not missing, f"no placement for {sorted(missing)}"
    for ref, c in comps.items():
        lib, name = c["fp"].split(":")
        fp = io.FootprintLoad(FP_LOCAL.get(lib, f"{FP_STOCK}/{lib}.pretty"), name)
        assert fp, c["fp"]
        fp.SetFPIDAsString(c["fp"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        for k, v in c["fields"].items():
            new = not fp.HasField(k)
            fp.SetField(k, v)
            if new:  # symbol-only fields (e.g. Sim.*) come in visible on the silkscreen
                fp.GetField(k).SetVisible(False)
        fp.SetPath(pcbnew.KIID_PATH(f"/{c['uuid']}"))
        x, y, rot, *side = place[ref]
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        board.Add(fp)
        if side == ["back"]:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if tidy:
            tidy(fp, ref)
        for pad in fp.Pads():
            net = pad_net.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])


def add_tracks(board, nets, preroute):
    """preroute: [(net, layer, width, [(x, y), ...]), ...] — fixed stubs laid down before autorouting."""
    for net, layer, width, pts in preroute:
        for a, b in zip(pts, pts[1:]):
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(pt(*a))
            tr.SetEnd(pt(*b))
            tr.SetWidth(mm(width))
            tr.SetLayer(board.GetLayerID(layer))
            tr.SetNet(nets[net])
            board.Add(tr)


def route(board, build, max_passes=100):
    dsn, ses = build / "route.dsn", build / "route.ses"
    assert pcbnew.ExportSpecctraDSN(board, str(dsn)), "DSN export failed"
    subprocess.run(["java", "-jar", JAR, "-de", str(dsn), "-do", str(ses), "-mp", str(max_passes),
                    "--gui.enabled=false"], check=True)
    assert pcbnew.ImportSpecctraSES(board, str(ses)), "SES import failed"
