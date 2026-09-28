#!/usr/bin/env python3
"""Generate the SaltMon carrier schematic (DepthSensor.kicad_sch).

Label-driven: every pin end gets a net label (or a no-connect flag), so the netlist is defined entirely by the
NETS tables below, which mirror docs/pinmap.md and docs/requirements.md §3–§6. Symbols are embedded from the
stock KiCad libraries and kicad/lib/SaltMon.kicad_sym.

Run:  python3 kicad/DepthSensor/gen_schematic.py
Check: kicad-cli sch erc kicad/DepthSensor/DepthSensor.kicad_sch
"""
import math
import re
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "DepthSensor.kicad_sch"
STOCK = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")
LOCAL = {"SaltMon": HERE.parent / "lib" / "SaltMon.kicad_sym"}
ROOT_UUID = "c60f782c-b422-45cf-a51e-6656e6b8da61"
PROJECT = "DepthSensor"
G = 2.54

# ---------------------------------------------------------------- s-expressions


def parse(s):
    tok = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')
    stack = [[]]
    for m in tok.finditer(s):
        t = m.group(0)
        if t == "(":
            stack.append([])
        elif t == ")":
            x = stack.pop()
            stack[-1].append(x)
        else:
            stack[-1].append(t)
    return stack[0][0]


def dump(n, ind=1):
    if not isinstance(n, list):
        return n
    if all(not isinstance(c, list) for c in n):
        return "(" + " ".join(n) + ")"
    pad = "\t" * ind
    head = [c for c in n if not isinstance(c, list)]
    body = [c for c in n if isinstance(c, list)]
    return "(" + " ".join(head) + "".join("\n" + pad + dump(c, ind + 1) for c in body) + ")"


def q(s):
    return '"' + s + '"'


def uq(s):
    return s[1:-1] if s.startswith('"') else s


_NS = uuid.UUID("5a1f0000-5a17-4d0e-8000-000000000000")
_seq = [0]


def u(key=None):
    """Deterministic UUIDs, so regenerating keeps the PCB's links to the symbols (and diffs small)."""
    if key is None:
        _seq[0] += 1
        key = f"item{_seq[0]}"
    return str(uuid.uuid5(_NS, key))


# ---------------------------------------------------------------- library access

_libs = {}


def lib(name):
    if name not in _libs:
        path = LOCAL.get(name, STOCK / f"{name}.kicad_sym")
        tree = parse(path.read_text())
        _libs[name] = {uq(x[1]): x for x in tree if isinstance(x, list) and x[0] == "symbol"}
    return _libs[name]


def flat_symbol(lib_id):
    """Return the lib symbol as a list, flattened if it uses (extends ...), renamed to lib_id."""
    ln, sn = lib_id.split(":")
    s = [list(x) if isinstance(x, list) else x for x in lib(ln)[sn]]
    ext = [x for x in s if isinstance(x, list) and x[0] == "extends"]
    if ext:
        parent = uq(ext[0][1])
        base = flat_symbol(f"{ln}:{parent}")
        child_props = {x[1]: x for x in s if isinstance(x, list) and x[0] == "property"}
        out = []
        for x in base:
            if isinstance(x, list) and x[0] == "property" and x[1] in child_props:
                out.append(child_props.pop(x[1]))
            elif isinstance(x, list) and x[0] == "symbol":
                y = list(x)
                y[1] = q(uq(y[1]).replace(parent, sn, 1))
                out.append(y)
            else:
                out.append(x)
        # remaining child-only properties go after the last property
        idx = max(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == "property") + 1
        out[idx:idx] = list(child_props.values())
        s = out
    s = list(s)
    s[1] = q(lib_id)
    return s


def pins_of(sym):
    out = []

    def walk(n):
        if isinstance(n, list):
            if n and n[0] == "pin" and len(n) > 2 and not isinstance(n[1], list):
                at = next(x for x in n if isinstance(x, list) and x[0] == "at")
                num = next(x for x in n if isinstance(x, list) and x[0] == "number")[1]
                out.append((uq(num), float(at[1]), float(at[2]), int(float(at[3]))))
            for c in n:
                walk(c)

    walk(sym)
    return out


def props_of(sym):
    return {uq(x[1]): x for x in sym if isinstance(x, list) and x[0] == "property"}


# ---------------------------------------------------------------- placement


def xf(px, py, X, Y, rot):
    a = math.radians(rot)
    x = px * math.cos(a) - py * math.sin(a)
    y = px * math.sin(a) + py * math.cos(a)
    return round(X + x, 4), round(Y - y, 4)


used = {}
items = []


def label_fx(angle):
    j = "left bottom" if angle in (0, 90) else "right bottom"
    return f'(effects (font (size 1.27 1.27)) (justify {j}))'


def place(lib_id, ref, value, X, Y, nets, rot=0, fp=None, fields=None, prop_at=None, bom=True):
    """nets: {pin_number: net_name | None (no-connect)}; pins missing from nets are an error."""
    sym = flat_symbol(lib_id)
    used[lib_id] = sym
    pins = pins_of(sym)
    missing = {p[0] for p in pins} - set(nets)
    extra = set(nets) - {p[0] for p in pins}
    assert not missing and not extra, (ref, missing, extra)
    lp = props_of(sym)
    vals = {"Reference": ref, "Value": value}
    if fp:
        vals["Footprint"] = fp
    vals.update(fields or {})
    props = []
    for key, p in lp.items():
        if key.startswith("ki_"):
            continue
        at = next(x for x in p if isinstance(x, list) and x[0] == "at")
        eff = next((x for x in p if isinstance(x, list) and x[0] == "effects"), None)
        hide = any(isinstance(x, list) and x[0] == "hide" for x in p)
        x, y = xf(float(at[1]), float(at[2]), X, Y, rot)
        ang = (int(float(at[3])) + rot) % 180 if len(at) > 3 else 0
        v = vals.get(key, uq(p[2]))
        if prop_at and key in prop_at:  # screen-relative (dx, dy); left-justified, horizontal
            dx, dy = prop_at[key]
            x, y, ang = round(X + dx, 4), round(Y + dy, 4), (360 - rot) % 180  # field angle is symbol-relative
            eff = ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", "left"]]
        props.append(f'(property "{key}" "{v}" (at {x} {y} {ang}){" (hide yes)" if hide else ""} {dump(eff) if eff else ""})')
    for key, v in (fields or {}).items():
        if key not in lp:
            props.append(f'(property "{key}" "{v}" (at {X} {Y} 0) (hide yes) (effects (font (size 1.27 1.27))))')
    pin_uuids = " ".join(f'(pin "{p[0]}" (uuid "{u()}"))' for p in pins)
    items.append(
        f'(symbol (lib_id "{lib_id}") (at {X} {Y} {rot}) (unit 1) (exclude_from_sim no) (in_bom {"yes" if bom else "no"}) (on_board yes) (dnp no)\n'
        f'\t\t(uuid "{u("sym:" + ref)}")\n\t\t' + "\n\t\t".join(props) + f"\n\t\t{pin_uuids}\n"
        f'\t\t(instances (project "{PROJECT}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1)))))')
    for num, px, py, prot in pins:
        x, y = xf(px, py, X, Y, rot)
        net = nets[num]
        if net is None:
            items.append(f'(no_connect (at {x} {y}) (uuid "{u()}"))')
        else:
            ang = (prot + rot + 180) % 360
            items.append(f'(label "{net}" (at {x} {y} {ang}) {label_fx(ang)} (uuid "{u()}"))')


def note(text, x, y, size=2.0):
    t = text.replace('"', '\\"').replace("\n", "\\n")
    items.append(f'(text "{t}" (exclude_from_sim no) (at {x} {y} 0) (effects (font (size {size} {size}) (thickness {size * 0.15:.2f}) (bold yes)) (justify left bottom)) (uuid "{u()}"))')


def text(t, x, y):
    t = t.replace('"', '\\"').replace("\n", "\\n")
    items.append(f'(text "{t}" (exclude_from_sim no) (at {x} {y} 0) (effects (font (size 1.27 1.27)) (justify left top)) (uuid "{u()}"))')


# ---------------------------------------------------------------- footprints

FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
FP_TP = "TestPoint:TestPoint_THTPad_1.5x1.5mm_Drill0.7mm"

# ---------------------------------------------------------------- 1. power input

note("1. POWER IN  (req §4)", 20.32, 25.4)
text("J1 center-positive 5 V -> F1 PTC -> lid switch (via J3 pins 11-14) -> D1 -> V_SYS (~4.6 V) -> kit 5V pin.\n"
     "Bench without lid: jumper plug on J3 shorting pins 11-14.", 20.32, 27.94)
place("Connector:Barrel_Jack_Switch", "J1", "PJ-102AH", G * 10, G * 18,
      {"1": "VIN_RAW", "2": "GND", "3": None}, fp="Connector_BarrelJack:BarrelJack_CUI_PJ-102AH_Horizontal")
place("Device:Polyfuse", "F1", "RXEF075", G * 24, G * 18, {"1": "VIN_RAW", "2": "SW_A"},
      fp="Fuse:Fuse_Bourns_MF-RHT070", fields={"Description": "PTC 0.75 A hold / 1.5 A trip, 5.1 mm radial"})
place("Diode:1N5822", "D1", "1N5822", G * 36, G * 18, {"1": "V_SYS", "2": "SW_B"}, rot=180)
place("Device:D_Zener", "D2", "P6KE6.8A", G * 48, G * 18, {"1": "V_SYS", "2": "GND"}, rot=270,
      fp="Diode_THT:D_DO-15_P10.16mm_Horizontal",
      fields={"Description": "Unidirectional TVS 600 W, 5.8 V standoff (optional)"},
      prop_at={"Reference": (2.54, -1.27), "Value": (2.54, 1.27)})
place("Device:C_Polarized", "C1", "220u 16V", G * 56, G * 18, {"1": "V_SYS", "2": "GND"},
      fp="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm")
place("Device:C", "C3", "100n", G * 64, G * 18, {"1": "V_SYS", "2": "GND"}, fp=FP_C)
place("power:PWR_FLAG", "#FLG01", "PWR_FLAG", G * 72, G * 16, {"1": "V_SYS"})
place("power:PWR_FLAG", "#FLG02", "PWR_FLAG", G * 78, G * 16, {"1": "GND"})

# ---------------------------------------------------------------- 2. MCU

note("2. MCU  ESP32-C6-DevKitM-1 (socketed)", 106.68, 88.9)
text("Strapping/USB/UART0 pins left open: GPIO4/5/8/9/15, 12/13, 16/17.\n"
     "3V3 comes from the kit LDO (feeds the US-100 only).", 106.68, 91.44)
U1 = {"1": "+3V3", "2": None, "3": "LED_CH1", "4": "LED_CH2", "5": None, "6": None, "7": "LED_CH3",
      "8": "LED_CH4", "9": None, "10": "LED_CH5", "11": "LED_CH6", "12": "LED_CH7", "13": "GND", "14": "V_SYS",
      "15": "GND",
      "16": "GND", "17": None, "18": None, "19": "SNS_RX", "20": "SNS_TX", "21": "SPARE_B", "22": "SPARE_A",
      "23": "BTN_N", "24": "LED_CH8", "25": None, "26": None, "27": "GND", "28": None, "29": None, "30": "GND"}
place("SaltMon:ESP32-C6-DevKitM-1", "U1", "ESP32-C6-DevKitM-1", G * 60, G * 50, U1)

# ---------------------------------------------------------------- 3. LED driver

note("3. LED DRIVER  (req §5.1)", 213.36, 25.4)
text("GPIO HIGH = LED on. RN1 pull-downs keep LEDs off through reset/boot.\n"
     "R1-R8 on the carrier; LED cathodes return on J3 pins 15/16.", 213.36, 27.94)
U2 = {str(i): f"LED_CH{i}" for i in range(1, 9)}
U2.update({str(19 - i): f"DRV_O{i}" for i in range(1, 9)})
U2.update({"9": "V_SYS", "10": "GND"})
place("Transistor_Array:TBD62783A", "U2", "TBD62783APG", G * 96, G * 28, U2,
      fp="Package_DIP:DIP-18_W7.62mm_Socket")
place("Device:C", "C2", "100n", G * 108, G * 22, {"1": "V_SYS", "2": "GND"}, fp=FP_C)
RN = {"1": "GND"}
RN.update({str(i + 1): f"LED_CH{i}" for i in range(1, 9)})
place("Device:R_Network08", "RN1", "100k", G * 96, G * 46, RN, fp="Resistor_THT:R_Array_SIP9")
LED_R = ["180", "300", "300", "300", "470", "470", "180", "300"]
LED_NAME = ["Green", "Yellow", "Orange", "Red", "Blue", "Purple", "Bi-Green", "Bi-Red"]
for i in range(8):
    place("Device:R", f"R{i + 1}", LED_R[i], G * (118 + 4 * i), G * 22,
          {"1": f"DRV_O{i + 1}", "2": f"LED_A{i + 1}"}, fp=FP_R, fields={"Description": LED_NAME[i]})
place("Device:R", "R9", "1k5", G * 150, G * 22, {"1": "V_SYS", "2": "LED_PWR"}, fp=FP_R,
      fields={"Description": "White power LED, ~1 mA"})

# ---------------------------------------------------------------- 4. lid panel

note("4. LID PANEL  J_PANEL (req §5.2)", 299.72, 88.9)
text("Shrouded 2x8, 16-way ribbon ~20 cm to the hand-wired lid.\nSW_A/SW_B each use two conductors.", 299.72, 91.44)
JP = {str(i): f"LED_A{i}" for i in range(1, 9)}
JP.update({"9": "LED_PWR", "10": "BTN_N", "11": "SW_A", "12": "SW_A", "13": "SW_B", "14": "SW_B",
           "15": "GND", "16": "GND"})
place("Connector_Generic:Conn_02x08_Odd_Even", "J3", "J_PANEL", G * 134, G * 48, JP,
      fp="Connector_IDC:IDC-Header_2x08_P2.54mm_Vertical")

# ---------------------------------------------------------------- 5. sensor

note("5. SENSOR  US-100 (UART mode)  J_SNS", 20.32, 185.42)
text("100 R + 1 nF on each data line (RC 100 ns). 6-way ribbon ~1.2 m; far end 1x5 Dupont.", 20.32, 187.96)
place("Device:R", "R11", "100", G * 12, G * 82, {"1": "SNS_TX", "2": "SNS_TX_C"}, fp=FP_R)
place("Device:R", "R12", "100", G * 20, G * 82, {"1": "SNS_RX", "2": "SNS_RX_C"}, fp=FP_R)
place("Device:C", "C7", "1n", G * 28, G * 82, {"1": "SNS_TX_C", "2": "GND"}, fp=FP_C)
place("Device:C", "C8", "1n", G * 36, G * 82, {"1": "SNS_RX_C", "2": "GND"}, fp=FP_C)
place("Device:C_Polarized", "C6", "10u", G * 44, G * 82, {"1": "+3V3", "2": "GND"},
      fp="Capacitor_THT:CP_Radial_D5.0mm_P2.00mm")
place("Device:C", "C4", "100n", G * 52, G * 82, {"1": "+3V3", "2": "GND"}, fp=FP_C)
place("Connector_Generic:Conn_02x03_Odd_Even", "J2", "J_SNS", G * 68, G * 82,
      {"1": "+3V3", "2": "SNS_TX_C", "3": "SNS_RX_C", "4": "GND", "5": "GND", "6": None},
      fp="Connector_IDC:IDC-Header_2x03_P2.54mm_Vertical")

# ---------------------------------------------------------------- 6. button, spare, test, mech

note("6. BUTTON / SPARE / TEST / MECH", 213.36, 185.42)
place("Device:R", "R10", "10k", G * 88, G * 82, {"1": "+3V3", "2": "BTN_N"}, fp=FP_R)
place("Device:C", "C5", "100n", G * 96, G * 82, {"1": "BTN_N", "2": "GND"}, fp=FP_C)
place("Connector_Generic:Conn_01x04", "J4", "J_SPARE", G * 112, G * 82,
      {"1": "+3V3", "2": "GND", "3": "SPARE_A", "4": "SPARE_B"},
      fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")
for i, net in enumerate(["V_SYS", "+3V3", "GND", "SNS_TX_C", "SNS_RX_C", "SW_A"]):
    place("Connector:TestPoint", f"TP{i + 1}", net, G * (88 + 6 * i), G * 96, {"1": net}, fp=FP_TP, bom=False)
for i in range(4):
    place("Mechanical:MountingHole", f"H{i + 1}", "M3", G * (88 + 6 * i), G * 104, {},
          fp="MountingHole:MountingHole_3.2mm_M3", bom=False)

# ---------------------------------------------------------------- write

lib_syms = "\n\t\t".join(dump(s, 3) for s in used.values())
OUT.write_text(
    "(kicad_sch\n\t(version 20260306)\n\t(generator \"eeschema\")\n\t(generator_version \"10.0\")\n"
    f'\t(uuid "{ROOT_UUID}")\n\t(paper "A3")\n'
    '\t(title_block (title "SaltMon carrier") (date "2026-09-28") (rev "0.1")\n'
    '\t\t(comment 1 "Generated by kicad/DepthSensor/gen_schematic.py - edit the script, not this file")\n'
    '\t\t(comment 2 "Pin map: docs/pinmap.md   Requirements: docs/requirements.md"))\n'
    f"\t(lib_symbols\n\t\t{lib_syms})\n\t" + "\n\t".join(items) +
    '\n\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n')
print("wrote", OUT)
