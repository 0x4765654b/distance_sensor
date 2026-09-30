#!/usr/bin/env python3
"""Generate the SaltMon carrier schematic (DepthSensor.kicad_sch).

Label-driven: every pin end gets a net label (or a no-connect flag), so the netlist is defined entirely by the
NETS tables below, which mirror docs/pinmap.md and docs/requirements.md §3–§6. Symbols are embedded from the
stock KiCad libraries and kicad/lib/SaltMon.kicad_sym (helpers in kicad/lib/schgen.py).

Run:  python3 kicad/DepthSensor/gen_schematic.py
Check: kicad-cli sch erc kicad/DepthSensor/DepthSensor.kicad_sch
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
from schgen import G, init, note, place, text, write  # noqa: E402

OUT = HERE / "DepthSensor.kicad_sch"
init("DepthSensor", "c60f782c-b422-45cf-a51e-6656e6b8da61", "5a1f0000-5a17-4d0e-8000-000000000000")

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

write(OUT, "SaltMon carrier", "2026-09-28", "0.1",
      ["Generated by kicad/DepthSensor/gen_schematic.py - edit the script, not this file",
       "Pin map: docs/pinmap.md   Requirements: docs/requirements.md"])
