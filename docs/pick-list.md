# SaltMon Pick List — carrier rev 0.2

One build. Refs match `kicad/DepthSensor/DepthSensor.kicad_sch`; the lid panel has its own list, [lid-pick-list.md](lid-pick-list.md); specs come from `docs/requirements.md` §3, §4 and §9.
Everything is through-hole. **Have** = the part is already on hand.

## 1. Carrier PCB — ICs, modules, sockets

| ✓ | Qty | Part | Refs | Notes |
|---|---|---|---|---|
| ☐ | 1 | ESP32-C6-DevKitM-1 (4 MB) | U1 | Espressif dev kit |
| ☐ | 2 | 1×15 female header, 2.54 mm, 8.5 mm tall | U1 socket | Rows are 22.86 mm apart; the height sets the USB-C position (MEC-04) |
| ☐ | 1 | TBD62783APG | U2 | Toshiba 8-channel source driver, DIP-18 |
| ☐ | 1 | DIP-18 socket, 7.62 mm | U2 socket | |
| ☐ | 1 | 8 × 100 kΩ bussed resistor network, SIP-9 | RN1 | Pin 1 is the common pin (e.g. Bourns 4609X-101-104LF) |

## 2. Carrier PCB — power

| ✓ | Qty | Part | Refs | Notes |
|---|---|---|---|---|
| ☐ | 1 | CUI PJ-102AH DC jack, 5.5 × 2.1 mm | J1 | |
| ☐ | 1 | PTC fuse, 0.75 A hold / 1.5 A trip, 5.1 mm lead pitch | F1 | Littelfuse RXEF075 or Bourns MF-R075 |
| ☐ | 1 | 1N5822 Schottky, DO-201AD | D1 | |
| ☐ | 1 | P6KE6.8A TVS, DO-15 | D2 | Optional |
| ☐ | 1 | 220 µF 16 V electrolytic, Ø8 mm, 3.5 mm pitch, ≤ 11.5 mm tall | C1 | The height matters (MEC-04) |

## 3. Carrier PCB — resistors (¼ W metal film, 10.16 mm pitch)

| ✓ | Qty | Value | Refs |
|---|---|---|---|
| ☐ | 2 | 100 Ω | R11, R12 |
| ☐ | 2 | 180 Ω | R1, R7 |
| ☐ | 4 | 300 Ω | R2, R3, R4, R8 |
| ☐ | 2 | 470 Ω | R5, R6 |
| ☐ | 1 | 1.5 kΩ | R9 |
| ☐ | 1 | 10 kΩ | R10 |

## 4. Carrier PCB — capacitors

| ✓ | Qty | Value | Refs | Package |
|---|---|---|---|---|
| ☐ | 4 | 100 nF ceramic | C2, C3, C4, C5 | Disc/MLCC, 5 mm pitch |
| ☐ | 2 | 1 nF ceramic | C7, C8 | Disc/MLCC, 5 mm pitch |
| ☐ | 1 | 10 µF 16 V electrolytic | C6 | Ø5 mm, 2 mm pitch |

## 5. Carrier PCB — connectors

| ✓ | Qty | Part | Refs | Notes |
|---|---|---|---|---|
| ☐ | 1 | 2×8 shrouded (keyed) box header, 2.54 mm, vertical | J3 (J_PANEL) | |
| ☐ | 1 | 2×3 shrouded (keyed) box header, 2.54 mm, vertical | J2 (J_SNS) | |
| ☐ | 1 | 1×4 male pin header, 2.54 mm | J4 (J_SPARE) | Optional |

TP1–TP6 are bare pads, and H1–H4 are holes, so there's nothing to buy for them.

## 6. Lid panel PCB

See [lid-pick-list.md](lid-pick-list.md): the board, LEDs, LED spacers, header, switch and button, mounting
hardware and the lid cable.

## 7. Sensor and cables

| ✓ | Qty | Part | Notes |
|---|---|---|---|
| ☐ | 1 (+1 spare) | US-100 ultrasonic module | Fit the UART-mode jumper |
| ☐ | ~1.3 m | 6-way 0.05" (1.27 mm) flat ribbon, 28 AWG | Sensor cable, about 1.2 m plus trim |
| ☐ | 1 | 2×3 IDC ribbon socket, 2.54 mm | Carrier end of the sensor cable |
| ☐ | 1 | 1×5 Dupont female housing + 5 crimp pins | Sensor end |
| ☐ | 1 | 2×8 IDC ribbon socket, 2.54 mm | Bench jumper plug (below). The lid cable is in the lid pick list |

**Bench jumper plug:** a spare 2×8 IDC socket with pins 11–14 shorted, so the board powers up without the lid attached (PWR-05).

## 8. Power supply

| ✓ | Qty | Part | Notes |
|---|---|---|---|
| ☐ | 1 | 5 V DC adapter, ≥ 1 A, 5.5 × 2.1 mm plug, center positive | Peak draw is about 480 mA |

## 9. Enclosure and hardware

| ✓ | Qty | Part | Notes |
|---|---|---|---|
| **Have** | 1 | Gasketed ABS junction box, about 115 × 90 × 55 mm | Mounted to the wall through its 4 corner holes (MEC-07) |
| ☐ | 4 | Wall screws + anchors for the box corners | Sized to the box's corner holes |
| ☐ | 4 | M3 × 6 mm nylon standoffs | Carrier to floor (MEC-05) |
| ☐ | 4 | M3 × 6 mm screws, nylon or stainless | Carrier to standoffs |
| ☐ | 4 | M3 screws + sealing washers | Standoffs through holes drilled in the floor |
| ☐ | 1 | Cable grommet or gland | Sensor ribbon exit in the side wall |
| ☐ | several | Small cable ties | One through the carrier's tie holes; more for strain relief |
| ☐ | 2 | Nylon M2 screws, nuts and spacers | US-100 mounted under the tank lid (SNS-04) |

## 10. Consumables

| ✓ | Part | Use |
|---|---|---|
| ☐ | Conformal coating | Back of the US-100 PCB only, not the transducers (SNS-05) |
| ☐ | Dielectric grease | Dupont contacts at the sensor |
| ☐ | Label | BLE proof-of-possession code, inside the box (SEC-01) |

## Tools you might not already have

- IDC ribbon crimp tool or a small vise, for the IDC sockets.
- Dupont crimper, for the sensor-end housing.
- A file for the USB-C cut-out (13 × 8 mm) and an 8 mm drill for the DC jack. Lid tools are in the lid pick list.
