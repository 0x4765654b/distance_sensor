#!/usr/bin/env python3
"""Generate the ESP32-C6-DevKitM-1 KiCad symbol and socketed footprint.

Geometry from docs/esp32-c6-devkitm-1-dimensions.pdf (v1.0):
  board 25.40 x 48.26 mm, header rows 22.86 mm apart (1.27 mm from each long edge),
  J1-15 / J3-15 is 11.125 mm from the USB edge, so pin 1 is 1.575 mm from the antenna edge,
  module antenna 13.20 mm wide overhangs the antenna edge by 5.37 mm.
Pinout from docs/esp32-c6-devkitm-1-schematics.pdf.

Pads 1-15 = J1-1..15, pads 16-30 = J3-1..15. Footprint origin = J1-1, viewed from the top of the
carrier with the kit plugged in (antenna toward -Y, USB toward +Y).

Run:  python3 kicad/lib/gen_devkit.py
"""
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "ESP32-C6-DevKitM-1"
FP_NAME = "ESP32-C6-DevKitM-1_Socketed"
DATASHEET = "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32c6/esp32-c6-devkitm-1/user_guide.html"

# (name, electrical type) per header pin, top (antenna end) to bottom (USB end)
J1 = [
    ("3V3", "power_out"), ("CHIP_PU", "input"), ("GPIO2", "bidirectional"),
    ("GPIO3", "bidirectional"), ("GPIO4/MTMS", "bidirectional"), ("GPIO5/MTDI", "bidirectional"),
    ("GPIO0", "bidirectional"), ("GPIO1", "bidirectional"), ("GPIO8/RGB_LED", "bidirectional"),
    ("GPIO6", "bidirectional"), ("GPIO7", "bidirectional"), ("GPIO14", "bidirectional"),
    ("GND", "power_in"), ("5V", "power_in"), ("GND", "passive"),
]
J3 = [
    ("GND", "passive"), ("GPIO16/U0TXD", "bidirectional"), ("GPIO17/U0RXD", "bidirectional"),
    ("GPIO23", "bidirectional"), ("GPIO22", "bidirectional"), ("GPIO21", "bidirectional"),
    ("GPIO20", "bidirectional"), ("GPIO19", "bidirectional"), ("GPIO18", "bidirectional"),
    ("GPIO15", "bidirectional"), ("GPIO9/BOOT", "bidirectional"), ("GND", "passive"),
    ("GPIO13/USB_D+", "bidirectional"), ("GPIO12/USB_D-", "bidirectional"), ("GND", "passive"),
]

PITCH = 2.54
ROW = 22.86
BOARD_W, BOARD_L = 25.40, 48.26
PIN1_FROM_TOP = BOARD_L - 11.125 - 14 * PITCH  # 1.575
ANT_W, ANT_OVER = 13.20, 5.37
ANT_X0 = 6.33 - 1.27  # module left edge 6.33 mm from board left edge (scaled from drawing)
KEEPOUT = 10.0  # extra clearance beyond the antenna overhang


def u():
    return str(uuid.uuid4())


def font(size=1.27):
    return f"(effects (font (size {size} {size})))"


def prop(key, val, x, y, hide=False, justify=None):
    j = f" (justify {justify})" if justify else ""
    h = " (hide yes)" if hide else ""
    return (f'\t\t(property "{key}" "{val}" (at {x} {y} 0){h}\n'
            f"\t\t\t(effects (font (size 1.27 1.27)){j}))\n")


def symbol():
    top = 7 * PITCH  # pin 1 at +17.78, pin 15 at -17.78
    half_w = 15.24
    body_h = top + 2 * PITCH
    pins = []
    for i, (n, t) in enumerate(J1):
        y = round(top - i * PITCH, 2)
        pins.append((str(i + 1), n, t, -(half_w + PITCH), y, 0, i == 14))
    for i, (n, t) in enumerate(J3):
        y = round(top - i * PITCH, 2)
        pins.append((str(i + 16), n, t, half_w + PITCH, y, 180, False))
    body = []
    for num, n, t, x, y, rot, _ in pins:
        body.append(
            f"\t\t\t(pin {t} line (at {x} {y} {rot}) (length 2.54)\n"
            f'\t\t\t\t(name "{n}" {font()})\n'
            f'\t\t\t\t(number "{num}" {font()}))\n')
    labels = (
        f'\t\t\t(text "J1" (at {-half_w + 1.27} {body_h - 1.27} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        f'\t\t\t(text "J3" (at {half_w - 1.27} {body_h - 1.27} 0) (effects (font (size 1.27 1.27)) (justify right)))\n'
        f'\t\t\t(text "ANT ↑  USB ↓" (at 0 {-body_h + 1.27} 0) (effects (font (size 1.27 1.27))))\n'
    )
    return (
        "(kicad_symbol_lib\n\t(version 20251024)\n\t(generator \"saltmon_gen_devkit\")\n\t(generator_version \"10.0\")\n"
        f'\t(symbol "{NAME}"\n'
        "\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)\n"
        + prop("Reference", "U", -half_w, body_h + 1.27, justify="left bottom")
        + prop("Value", NAME, half_w, body_h + 1.27, justify="right bottom")
        + prop("Footprint", f"SaltMon:{FP_NAME}", 0, -body_h - 3.81, hide=True)
        + prop("Datasheet", DATASHEET, 0, -body_h - 6.35, hide=True)
        + prop("Description",
               "Espressif ESP32-C6-DevKitM-1 (4 MB flash), plugged into 2x 1x15 female headers 22.86 mm apart. "
               "Pads 1-15 = J1-1..15, 16-30 = J3-1..15. Avoid strapping GPIO4/5/8/9/15, USB 12/13, UART0 16/17.",
               0, -body_h - 8.89, hide=True)
        + prop("ki_keywords", "ESP32 ESP32-C6 devkit WiFi6 BLE Zigbee Thread", 0, 0, hide=True)
        + prop("ki_fp_filters", "ESP32?C6?DevKitM?1*", 0, 0, hide=True)
        + f'\t\t(symbol "{NAME}_0_1"\n'
        f"\t\t\t(rectangle (start {-half_w} {body_h}) (end {half_w} {-body_h})\n"
        "\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background)))\n"
        + labels + "\t\t)\n"
        f'\t\t(symbol "{NAME}_1_1"\n' + "".join(body) + "\t\t)\n"
        "\t\t(embedded_fonts no)\n\t)\n)\n"
    )


def line(x0, y0, x1, y1, layer, w=0.12):
    return (f"\t(fp_line (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f})\n"
            f'\t\t(stroke (width {w}) (type solid)) (layer "{layer}") (uuid "{u()}"))\n')


def rect(x0, y0, x1, y1, layer, w=0.12):
    return (f"\t(fp_rect (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f})\n"
            f'\t\t(stroke (width {w}) (type solid)) (fill no) (layer "{layer}") (uuid "{u()}"))\n')


def text(s, x, y, layer, size=1.0):
    return (f'\t(fp_text user "{s}" (at {x:.3f} {y:.3f} 0) (layer "{layer}") (uuid "{u()}")\n'
            f"\t\t(effects (font (size {size} {size}) (thickness {size * 0.15:.2f}))))\n")


def footprint():
    bx0, by0 = -1.27, -PIN1_FROM_TOP
    bx1, by1 = bx0 + BOARD_W, by0 + BOARD_L
    ax0, ax1 = ANT_X0, ANT_X0 + ANT_W
    ay0 = by0 - ANT_OVER
    out = [
        f'(footprint "{FP_NAME}"\n\t(version 20260206)\n\t(generator "saltmon_gen_devkit")\n\t(layer "F.Cu")\n'
        f'\t(descr "ESP32-C6-DevKitM-1 on 2x PinSocket_1x15_P2.54mm, rows 22.86 mm. Includes antenna overhang '
        f'and a copper keep-out {KEEPOUT:g} mm beyond it. {DATASHEET}")\n'
        '\t(tags "ESP32 ESP32-C6 DevKitM-1 socket")\n',
        f'\t(property "Reference" "REF**" (at {bx0 + BOARD_W / 2:.3f} {by1 + 1.8:.3f} 0) (layer "F.SilkS") (uuid "{u()}")\n'
        "\t\t(effects (font (size 1 1) (thickness 0.15))))\n",
        f'\t(property "Value" "{NAME}" (at {bx0 + BOARD_W / 2:.3f} {by0 + BOARD_L / 2:.3f} 90) (layer "F.Fab") (uuid "{u()}")\n'
        "\t\t(effects (font (size 1 1) (thickness 0.15))))\n",
        "\t(attr through_hole)\n",
    ]
    # kit outline and antenna
    out.append(rect(bx0, by0, bx1, by1, "F.Fab", 0.1))
    out.append(rect(ax0, ay0, ax1, by0, "F.Fab", 0.1))
    out.append(text("ANTENNA", (ax0 + ax1) / 2, ay0 + ANT_OVER / 2, "F.Fab", 0.8))
    out.append(text("USB-C (UART | USB)", bx0 + BOARD_W / 2, by1 - 4.0, "F.Fab", 0.8))
    out.append(text("${REFERENCE}", bx0 + BOARD_W / 2, by0 + 8, "F.Fab", 1.0))
    # silkscreen: kit long sides only (clear of pads), pin-1 mark, header labels. The ends sit on the carrier's
    # antenna slot and board edge, so they (and the antenna) are Fab-only.
    s = 0.11
    for x in (bx0 - s, bx1 + s):
        out.append(line(x, by0 + 1.0, x, by1 - 1.0, "F.SilkS"))
    out.append(line(-2.2, -1.0, -2.2, 1.0, "F.SilkS", 0.2))
    out.append(text("J1", 2.3, -0.2, "F.SilkS", 0.8))
    out.append(text("J3", ROW - 2.3, -0.2, "F.SilkS", 0.8))
    out.append(text("USB", bx0 + BOARD_W / 2, by1 - 1.6, "F.SilkS", 1.0))
    # courtyard: kit + antenna
    c = 0.5
    cy0 = ay0 - c
    pts = [(bx0 - c, by0 - c), (ax0 - c, by0 - c), (ax0 - c, cy0), (ax1 + c, cy0), (ax1 + c, by0 - c),
           (bx1 + c, by0 - c), (bx1 + c, by1 + c), (bx0 - c, by1 + c)]
    out.append("\t(fp_poly (pts " + " ".join(f"(xy {x:.3f} {y:.3f})" for x, y in pts) + ")\n"
               f'\t\t(stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd") (uuid "{u()}"))\n')
    # antenna keep-out (all copper, both layers)
    kx0, kx1 = bx0, bx1
    ky0, ky1 = ay0 - KEEPOUT, by0
    out.append(
        "\t(zone (layers \"F.Cu\" \"B.Cu\") (uuid \"" + u() + "\") (name \"ANT_KEEPOUT\") (hatch full 0.5)\n"
        "\t\t(connect_pads (clearance 0)) (min_thickness 0.25)\n"
        "\t\t(keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints allowed))\n"
        "\t\t(placement (enabled no) (sheetname \"\"))\n"
        "\t\t(fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))\n"
        f"\t\t(polygon (pts (xy {kx0:.3f} {ky0:.3f}) (xy {kx1:.3f} {ky0:.3f}) (xy {kx1:.3f} {ky1:.3f}) (xy {kx0:.3f} {ky1:.3f}))))\n")
    out.append(text("ANT KEEP-OUT: no copper; route slot in carrier", (kx0 + kx1) / 2, ky0 + 2, "Cmts.User", 0.7))
    # pads
    for col, x in ((0, 0.0), (1, ROW)):
        for i in range(15):
            num = i + 1 + 15 * col
            shape = "rect" if num == 1 else "circle"
            out.append(f'\t(pad "{num}" thru_hole {shape} (at {x:.3f} {i * PITCH:.3f}) (size 1.7 1.7) (drill 1)\n'
                       f'\t\t(layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{u()}"))\n')
    out.append("\t(embedded_fonts no)\n")
    for x in (0.0, ROW):
        out.append('\t(model "${KICAD10_3DMODEL_DIR}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x15_P2.54mm_Vertical.step"\n'
                   f"\t\t(offset (xyz {x:.3f} 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))\n")
    out.append(")\n")
    return "".join(out)


if __name__ == "__main__":
    (HERE / "SaltMon.kicad_sym").write_text(symbol())
    pretty = HERE / "SaltMon.pretty"
    pretty.mkdir(exist_ok=True)
    (pretty / f"{FP_NAME}.kicad_mod").write_text(footprint())
    print("wrote", HERE / "SaltMon.kicad_sym", pretty / f"{FP_NAME}.kicad_mod")
