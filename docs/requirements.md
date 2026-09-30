# Salt Level Monitor — System Requirements

Status: **DRAFT v0.8** (2026-09-30) — design phase. Covers the hardware (carrier PCB + passive lid panel PCB), device firmware, the `SaltMon` AWS stack, and the ChoreCore consumer contract. Open items are in [§12](#12-open-questions).

Reference docs in `docs/`:
- `4019_Web.pdf` — Adafruit US-100
- `esp32-c6-devkitm-1-schematics.pdf`, `-dimensions.pdf`, `-dimensions.dxf` — ESP32-C6-DevKitM-1 v1.0
- Culligan Gold Series Owner's Guide (P/N 01018854): <https://www.culligan.com/wp-content/uploads/2019/07pdf/Gold_Softener_01018854.pdf>
- `esp-dev-kits-en-master-esp32s3.pdf`, `models/ESP32_S3_DEVKITM_1_N8/` — **not used** (D-02)

### Proposed repository layout

```
docs/       requirements, pin map, ICDs, datasheets
kicad/      DepthSensor carrier PCB (KiCad 10)
firmware/   ESP-IDF v5.x application
cloud/      SaltMon-<env> CDK stack (TypeScript) + Python Lambdas
tools/      provision.py, saltmon-config.py
```

The ChoreCore consumer feature lives in `~/github/chorecore` (§8.7).

---

## 1. Product Summary

A monitor for the salt tank of a **Culligan Gold Series (9" media tank)** water softener.
A US-100 ultrasonic sensor mounted **on the underside of the salt tank lid** looks down at
the salt. It connects over a ribbon cable to a **wall-mounted enclosure** nearby. The enclosure
holds an ESP32-C6, which works out the salt level, shows it on the lid LEDs, and publishes
readings to **AWS IoT Core**. A **SaltMon** AWS stack in this repo stores the history, forecasts
when salt will run out, and publishes the results. The **ChoreCore** household app consumes them and creates an "Add salt" chore when it is time.

### 1.1 Salt Tank & Installation Geometry

From the Culligan Gold Series specification: the user's **375 lb** salt tank is **18 in dia × 43 in** (45.7 × 109 cm). It has a salt support plate, a Dubl-Safe brine valve inside a brine chamber tube at the side of the tank, and water kept about 1 in above the support plate. Culligan says to fill salt "to within a few inches of the top".

```
     wall-mounted enclosure                    salt tank lid (removable for refills)
   ┌───────────────────┐                  ┌───────────────────────────────┐
   │ LEDs, switch, btn │   ribbon cable   │  ▼▼ US-100 on underside       │
   │  (front panel)    │══════════════════╪══╝  offset away from brine    │
   │  [carrier + ESP32]│  (~1.2 m, slack  │      chamber                  │
   └───┬───┬───┬───────┘   for lid lift)  │                               │
      jack USB cable                      │   d ≈ 8–15 cm   salt, full    │ ║ brine
                                          │                               │ ║ chamber
                                          │   15° beam                    │ ║ tube
                                          │   d_low         refill point  │ ║
                                          │   ~~~ water ~1 in above plate │ ║
                                          │ ═══ salt support plate ═══    │ ║
                                          └───────────────────────────────┘
                                             109 cm (43 in) tall, 45.7 cm dia
```

| ID | Requirement |
|---|---|
| GEO-01 | Measurement range 5–110 cm. The US-100 is specified for 2–450 cm (best 10–250 cm). Accuracy ±(0.3 cm + 1%). |
| GEO-02 | Mount the sensor on the lid underside with the transducers pointing straight down, **3–5 cm off the tank center, on the side away from the brine chamber**. The beam footprint radius is about 0.13 × depth (≈ 14 cm at the plate). The tank radius is 22.9 cm, so the brine-chamber tube and the walls stay out of the beam down to the plate. |
| GEO-03 | Readings < 50 mm → `OBSTRUCTED` (salt piled against the sensor, or the lid is off and something is in front of it). |
| GEO-04 | The salt support plate is **1 in (25 mm) above the tank floor**, and the water sits about 1 in above the plate. Measured from the lid underside (≈ tank top, 1092 mm), that puts the plate at about 1067 mm and the water at about 1041 mm. Defaults until calibrated: `d_full` = 150 mm (salt a few inches below the top), **`d_low` = 900 mm** (salt ≈ 5½ in above the water ≈ 55 lb left, enough for a few regenerations). At install, record the real `d_plate` with the tank low and set `d_low` = `d_plate` − 170 mm. |
| GEO-05 | **Salt mass estimate (cloud):** 18 in dia → 254 in² of cross-section. At a salt bulk density of about 70 lb/ft³ (configurable), that is about **10.3 lb per inch** of salt height (≈ 4.1 lb/cm). A 40 lb bag raises the level by about 4 in. |
| GEO-06 | The lid is lifted at every refill. The cable needs enough slack and strain relief at both ends, and it unplugs at the sensor end. |

### 1.2 System Block Diagram

```
 ┌──────────────────────────── Carrier PCB (enclosure floor) ─────────────────────────────┐
 │ J1 jack ─► F1 PTC ─► (J_PANEL: lid switch)  ─► D1 Schottky ─► V_SYS ~4.6 V             │
 │                                                                  │                      │
 │  ESP32-C6-DevKitM-1 (socketed) ◄── 5V pin ───────────────────────┤                      │
 │     3V3 ─────────────────────────────────► J_SNS (2×3 IDC) ══ ribbon ══► US-100 (lid)   │
 │     GPIO22/23 UART1 ─── 100 Ω ───────────► J_SNS                                        │
 │     GPIO ×8 ─► U2 TBD62783APG ─► R ×8 ───► J_PANEL (2×8 IDC)                            │
 │     GPIO19 ◄── button ───────────────────── J_PANEL                                     │
 │  V_SYS ─► R_PWR ─────────────────────────► J_PANEL                                      │
 └────────────────────────────────────────────────────╥────────────────────────────────────┘
                                                      ║ 16-way IDC ribbon, ~20 cm, IDC socket each end, 1:1
 ┌──────────── Lid panel PCB (behind the lid) ────────╨───────────┐
 │  8 × 5 mm flat-top LEDs · pads for panel switch + push-button  │
 └────────────────────────────────────────────────────────────────┘
       Wi-Fi 2.4 GHz ─► router ─► AWS IoT Core ─► SaltMon stack (ingest · history · forecast) ─► SNS ─► ChoreCore (chore · reminders · UI)
```

---

## 2. Design Decisions Log

| ID | Decision | Rationale |
|---|---|---|
| D-01 | Monitor the salt level for a Culligan Gold Series (9") softener. | User |
| D-02 | ESP32-C6-DevKitM-1. | User |
| D-03 | Barrel jack on the carrier PCB. Power switch on the housing. | User |
| D-04 | All through-hole parts. Dev kit and US-100 are removable (they plug into headers). | User |
| D-05 | The US-100 sits **on the underside of the tank lid, connected by ribbon cable**. The enclosure is **wall-mounted** nearby. | User. The enclosure no longer has to sit on the tank. |
| D-06 | Enclosure: user's unlabeled **ABS gasketed junction box**, about 4.5 × 3.5 × 2 in (≈ 115 × 90 × 55 mm class). It has a deep base, a tray-style lid, brass inserts at the corners, and PCB bosses in the floor (§9). The RadioShack 270-1801 is rejected. | Fits the carrier + kit + lid wiring with margin. The gasket helps in a humid utility room. |
| D-07 | LED driver: TBD62783APG (8-ch source driver). All cathodes go to GND. | Through-hole; 3.3 V inputs; suits the common-cathode bi-color LED. |
| D-08 | White power LED is hard-wired to V_SYS. | "Power stays on dimly" |
| D-09 | Separate indicators for network status (bi-color), network activity (Blue), and sensor activity (Purple). | User |
| D-10 | **Lid panel PCB** (`kicad/LidPanel`, 50 × 63 mm, passive) on standoffs behind the lid. It holds the 8 flat-top LEDs, solder pads for the panel-mounted switch and button, and J_LID, a right-angle 2×8 shrouded header wired 1:1 to J_PANEL. The resistors, driver and pull-up stay on the carrier. The switch and button stay panel-mounted so the lid seals. | Replaces the hand-wired lid (v0.7): no fanned-out ribbon, no GND bus wire, and the board doubles as a drilling jig. The lid still unplugs from the carrier with one connector. |
| D-11 | Power switch = user's panel-mount SPDT mini slide switch (**2 A, 125 V AC**), used as SPST (common + one throw). F1 = **0.75 A hold**. | 2 A is about 4× the 480 mA peak. The 0.75 A fuse protects the 28 AWG ribbon conductors in the switch loop. |
| D-12 | Sensor cable = 6-way 0.05" flat ribbon, **keyed 2×3 IDC** at the carrier and a 1×5 2.54 mm Dupont housing at the sensor. | The keyed carrier end can't be plugged in backwards. The sensor end plugs onto the US-100's own header. |
| D-13 | Reverse-polarity protection is a series Schottky diode. | Also blocks backfeed from the kit's 5V/USB supply. |
| D-14 | US-100 runs in UART mode at 3.3 V. | Simple, temperature-compensated, direct logic levels. |
| D-15 | Device ↔ cloud via AWS IoT Core MQTT/TLS, one X.509 certificate per device. Firmware on ESP-IDF v5.x. | User's AWS stack |
| D-16 | **Two stacks.** `SaltMon-<env>` (this repo) owns IoT, history, and the forecast, and publishes records to SNS. `ChoreCore-<env>` adds a consumer feature that turns them into chores and UI. They are coupled only by the SNS contract (§8.3) through SSM. Account 345482189436 / us-east-1. | User. The device side stays reusable, and ChoreCore stays free of IoT concerns. |
| D-19 | The "Add salt" chore is **forecast-driven** (days to refill ≤ 3 based on history), with REFILL state as the fallback. It is assigned to Jeff Harman. | User |
| D-17 | The device computes level and alerts locally. It also publishes raw burst statistics. | LEDs keep working offline; the cloud can recompute from the raw data. |
| D-18 | USB-C (UART port) reachable **with the lid on** through a cut-out in the enclosure wall. | User |

---

## 3. Components

### 3.1 Carrier PCB

| Ref | Part | Package | Notes |
|---|---|---|---|
| U1 | ESP32-C6-DevKitM-1 | 2 × 1×15 female headers, rows **22.86 mm** apart | 25.4 × 48.26 mm; antenna overhangs 5.37 mm; 4 MB flash |
| U2 | TBD62783APG | DIP-18 in a socket | VIN(ON) ≥ 2.0 V |
| J1 | 5.5 × 2.1 mm DC jack (e.g. CUI PJ-102AH) | THT | Center-positive, at the bottom board edge |
| F1 | PTC, **0.75 A hold / 1.5 A trip** (e.g. Littelfuse RXEF075) | Radial | |
| D1 | 1N5822 Schottky | DO-201AD | |
| D2 | P6KE6.8A TVS (optional) | DO-15 | |
| C1 | 220 µF 16 V | Radial | V_SYS bulk |
| C2–C5 | 100 nF | Radial | Decoupling |
| C6 | 10 µF | Radial | At J_SNS VCC |
| C7, C8 | 1 nF | Radial | Sensor TX/RX filter to GND (RC = 100 ns with 100 Ω; a 9600-baud bit is 104 µs) |
| R | 1/4 W film | Axial | LED current, series, pull resistors |
| RN1 | 8 × 100 kΩ bussed network (common to GND) | SIP-9 | U2 input pull-downs (LED-02) |
| TP1–TP6 | Test pads: V_SYS, 3V3, GND, SNS_TX_C, SNS_RX_C, SW_A | THT pad | |
| J_SNS | 2×3 **shrouded (keyed)** box header, 2.54 mm | THT | Sensor ribbon |
| J_PANEL | 2×8 **shrouded (keyed)** box header, 2.54 mm | THT | Lid wiring ribbon |
| J_SPARE | 1×4 male header (3V3, GND, GPIO20, GPIO21) | THT | |

### 3.2 Lid Panel Parts (`kicad/LidPanel`)

| Ref | Part | Notes |
|---|---|---|
| D1–D8 | 5 mm **flat-top** LEDs: D1 Green, D2 Yellow, D3 Orange, D4 Red, D5 Blue, D6 Purple, D7 Bi-color R/G (3-lead common cathode, assumed pin order R / K / G: check the part), D8 White | Soldered to the lid board on 10 mm nylon LED spacers. The body goes through a Ø5.0 mm lid hole and the flange stops against the inside of the lid (no bezels). **The current resistors stay on the carrier.** |
| J1 (J_LID) | 2×8 shrouded box header, 2.54 mm, **right-angle** | On the back of the board; the ribbon leaves toward the top wall. |
| SW1 | User's SPDT mini slide switch, panel mount, 2 A / 125 V AC | Rectangular slot in the lid plus 2 screw holes (measure the part). Common pin and one throw pin wired to board pads J2 (SW_A, SW_B). |
| SW2 | Momentary panel push-button, normally open, 7 mm or 12 mm threaded bushing (e.g. PBS-110 / 16 mm "R13-507" class) | To be purchased. Wired to board pads J3 (BTN, GND). |
| H1–H4 | M3 mounting holes, 43 × 56 mm pitch | MEC-09 |

### 3.3 Cables

| Cable | Construction |
|---|---|
| Sensor | 6-way 0.05" flat ribbon, 28 AWG, **~1.2 m** (0.6 m run + slack so the lid can be lifted and set aside). Carrier end: 2×3 IDC socket. Sensor end: conductors 1–5 crimped into a 1×5 Dupont female housing (VCC, TX, RX, GND, GND); conductor 6 not used. Pin-1 stripe = VCC. Strain relief at both ends. |
| Lid | 16-way 0.05" flat ribbon, ~20 cm (enough to open the lid and lay it beside the box). A 2×8 IDC socket at **each end**, crimped 1:1 with the pin-1 stripe at the pin-1 mark of both sockets (J_PANEL pin *n* = J_LID pin *n*). |

---

## 4. Power Requirements

| ID | Requirement |
|---|---|
| PWR-01 | Input 5 V DC ±5% on a 5.5 × 2.1 mm center-positive jack. Adapter ≥ 1 A. |
| PWR-02 | Power path: J1 → F1 → J_PANEL (SW_A) → lid SW1 → J_PANEL (SW_B) → D1 → V_SYS. SW_A and SW_B each use **two** ribbon conductors. |
| PWR-03 | Reverse polarity: D1 blocks it. |
| PWR-04 | Overcurrent: F1 (0.75 A hold) trips on a V_SYS short, or on a short in the panel or sensor harness. |
| PWR-05 | Unplugging the lid ribbon opens the power path, so the device is OFF. This is a safe failure. For bench work without the lid, plug in a J_PANEL jumper plug (pins 11–14 shorted). |
| PWR-06 | USB and the jack may be connected at the same time (the kit has 1N5819 diodes on VBUS, and D1 blocks the reverse direction). With SW1 OFF and USB connected, the board runs from USB. |
| PWR-07 | 3V3 (from the kit LDO) powers the ESP32 and the US-100 only. |
| PWR-08 | Wi-Fi stays connected; modem-sleep is allowed. |

### 4.1 Power Budget (V_SYS)

| Load | Typical | Peak |
|---|---|---|
| ESP32-C6, Wi-Fi connected | 25–40 mA | ~350 mA |
| Kit overhead | 15 mA | 60 mA |
| US-100 | 2 mA | 10 mA |
| LEDs (power + dim level + dim net status) | ~3 mA | ~55 mA (self-test) |
| **Total** | **~60 mA** | **~480 mA** |

---

## 5. LED & Lid Panel Requirements

### 5.1 Electrical

| ID | Requirement |
|---|---|
| LED-01 | U2 VCC = V_SYS. The GPIO drive U2 IN1–8. The outputs go through current resistors **on the carrier**, then through J_PANEL to the LED anodes. The LED cathodes go to GND. |
| LED-02 | GPIO HIGH = LED on. Each U2 input has a 100 kΩ pull-down, so all driven LEDs stay off during reset and boot. |
| LED-03 | LEDC PWM on CH1–4 and CH7–8 (the C6's 6 LEDC channels). CH5–6 are plain GPIO outputs. PWM ≥ 1 kHz, ≥ 8-bit. |
| LED-04 | The White power LED is fed from V_SYS through R_PWR on the carrier (1.5 kΩ, about 1 mA). |

| Ch | LED | R | I | Drive | GPIO |
|---|---|---|---|---|---|
| CH1 | Green — level FULL | 180 Ω | 7.8 mA | LEDC0 | GPIO2 |
| CH2 | Yellow — level MID | 300 Ω | 8 mA | LEDC1 | GPIO3 |
| CH3 | Orange — level LOW-ish | 300 Ω | 8 mA | LEDC2 | GPIO0 |
| CH4 | Red — REFILL | 300 Ω | 8 mA | LEDC3 | GPIO1 |
| CH5 | Blue — network activity | 470 Ω | 3 mA | GPIO | GPIO6 |
| CH6 | Purple — sensor activity | 470 Ω | 3 mA | GPIO | GPIO7 |
| CH7 | Bi-color Green — network status | 180 Ω | 7.8 mA | LEDC4 | GPIO14 |
| CH8 | Bi-color Red — network status | 300 Ω | 8 mA | LEDC5 | GPIO18 |
| PWR | White — power | 1.5 kΩ | ~1 mA | hard-wired | — |

### 5.2 J_PANEL Pinout (2×8, 16-way ribbon)

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | CH1 Green | 2 | CH2 Yellow |
| 3 | CH3 Orange | 4 | CH4 Red |
| 5 | CH5 Blue | 6 | CH6 Purple |
| 7 | CH7 Bi-Green | 8 | CH8 Bi-Red |
| 9 | PWR LED (via R_PWR) | 10 | BTN (to GPIO19; pull-up is on the carrier) |
| 11 | SW_A (from F1) | 12 | SW_A |
| 13 | SW_B (to D1) | 14 | SW_B |
| 15 | GND | 16 | GND |

### 5.3 Lid Layout (lid = front face when wall-mounted; drilling template: MEC-06)

```
   Viewed from outside, portrait, bottom wall down. mm from the lid's inside top-left corner.
   ┌──────────── 82.6 ────────────┐
   │                              │
   │    x 26.3         x 56.3     │
   │    ● FULL         ● PWR      │  y 35
   │    ● MID          ● NET      │  y 46
   │    ● LOW          ● DATA     │  y 57
   │    ● REFILL       ● SENS     │  y 68
   │                              │
   │    [ON|OFF]        (BTN)     │  y 88   (x 30, x 52)
   │                              │
   └──────────────────────────────┘ 108
```

### 5.4 Indicator Behavior

| Indicator | LED | Pattern |
|---|---|---|
| Power | White | Steady and dim whenever V_SYS is present (hard-wired) |
| Salt level | G / Y / O / R | One LED steady and dim for the current band (≥ 75 / 40–75 / 15–40 / < 15 %). **REFILL:** Red blinks at 1 Hz, bright. **Bridge suspected:** the current LED double-blinks every 5 s. **Uncalibrated / obstructed:** a G→R chase every 10 s. **Sensor fault:** level LEDs off |
| Network status | Bi-color | Green steady (dim) = connected to AWS IoT · Amber = Wi-Fi only · Red 1 Hz = no Wi-Fi · Red 4 Hz = TLS/authentication failure · R/G alternating 2 Hz = BLE provisioning |
| Network activity | Blue | 50 ms flash on each acknowledged publish or received message |
| Sensor activity | Purple | 30 ms flash on each reading. 4 Hz continuous = sensor fault |
| Self-test | CH1–8 | Each lights for 200 ms at boot |

---

## 6. Sensor, MCU & I/O Requirements

| ID | Requirement |
|---|---|
| SNS-01 | US-100 in UART mode (rear jumper fitted), 9600 baud 8N1, 3V3 supply. |
| SNS-02 | Connection via J_SNS (2×3 keyed IDC): 1 = 3V3, 2 = SNS_TX (ESP→US-100 Echo/RX), 3 = SNS_RX (US-100 Trig/TX→ESP), 4 = GND, 5 = GND, 6 = NC. |
| SNS-03 | 100 Ω series resistors plus 1 nF to GND on both data lines at J_SNS. 10 µF + 100 nF across 3V3 at J_SNS. |
| SNS-04 | The sensor is mounted on the lid underside with nylon M2 hardware, or in a small bracket through its mounting holes. Transducers pointing straight down (GEO-02). |
| SNS-05 | **Brine-tank air is humid and salty.** Conformal-coat the rear of the US-100 PCB (not the transducers). Put dielectric grease on the Dupont contacts. Treat the sensor as a replaceable part and keep a spare. |
| MCU-01 | The dev kit sits in female headers **with its USB-C ports facing the bottom wall of the enclosure**. There is a cut-out for the UART USB-C port (D-18). The antenna end therefore points up, into the enclosure. |
| MCU-02 | **Antenna keep-out:** no copper on either layer, no connectors or ribbons, within 15 mm of the module antenna. Put a **routed cut-out** in the carrier under the antenna overhang. The enclosure lid is plastic. |
| MCU-03 | Pins to avoid: GPIO4, 5, 8, 9, 15 (strapping; 8 = RGB LED, 9 = BOOT), 12/13 (USB), 16/17 (UART0). |
| MCU-04 | Test points: V_IN, V_SYS, 3V3, GND, SNS_TX, SNS_RX. |

### 6.1 Pin Map

| Signal | GPIO | Kit pin |
|---|---|---|
| CH1–CH4 | 2, 3, 0, 1 | J1-3, J1-4, J1-7, J1-8 |
| CH5, CH6 | 6, 7 | J1-10, J1-11 |
| CH7, CH8 | 14, 18 | J1-12, J3-9 |
| Button | 19 | J3-8 |
| UART1 TX / RX | 22 / 23 | J3-5 / J3-4 |
| Spare | 20, 21 | J3-7, J3-6 |

---

## 7. Firmware Requirements

### 7.1 Platform

| ID | Requirement |
|---|---|
| FW-01 | ESP-IDF v5.x. FreeRTOS tasks: sensor, level/state, LED, network, button. |
| FW-02 | Partitions (4 MB): `nvs`, `nvs_keys`, `esp_secure_cert`, `otadata`, `phy_init`, `ota_0` / `ota_1` (~1.9 MB each). |
| FW-03 | Task watchdog and brownout detector enabled. Reset reason published at boot. |

### 7.2 Measurement & Level

| ID | Requirement |
|---|---|
| FW-10 | Every `sample_interval_s` (default 600 s), run a burst of 15 readings 100 ms apart. A reading of 0 or > 4500 mm is invalid. A burst is invalid if fewer than 8 readings are valid. |
| FW-11 | For each burst, record median, min, max, and valid count, plus the temperature (0x50 → value − 45 °C). |
| FW-12 | Level is the median of the last 6 bursts (1 h). `level_pct = (d_low − d)/(d_low − d_full)`, clamped to 0–100. |
| FW-13 | REFILL is set when the level stays below `refill_pct` (15%) for 3 consecutive hours. It clears only when a refill is detected (≥ 20-point rise within 1 h). |
| FW-14 | A detected refill publishes an event. If the new top is more than 5 cm from `d_full`, prompt re-calibration. |
| FW-15 | Salt-bridge hint: the level stays within ±1 cm for ≥ `bridge_days` (14). |
| FW-16 | Sensor fault: no valid burst for 30 min. OBSTRUCTED: median < 50 mm. |
| FW-17 | Lid-lift handling: a sudden jump to OBSTRUCTED or an implausible reading during a refill is **not** treated as a fault until it has lasted 30 min. |

### 7.3 Button

| Press | Action |
|---|---|
| < 1 s | All indicators bright for 30 s, then an immediate burst and publish |
| Hold 3 s | "Just refilled": set `d_full` from the current reading |
| Hold 10 s | BLE Wi-Fi provisioning mode (10 min) |
| Hold 20 s | Factory reset (Wi-Fi credentials and calibration). The AWS certificate is kept |

### 7.4 Connectivity (device side)

| ID | Requirement |
|---|---|
| CLD-01 | Connect to the AWS IoT ATS endpoint on port 8883 using MQTT 3.1.1 over TLS 1.2 with mutual X.509 authentication. Amazon Root CA 1 is embedded in the firmware. |
| CLD-02 | Thing name `saltmon-<MAC[3..5]>`. The client ID is the same as the thing name. The IoT endpoint and thing name are read from factory NVS (§8.4). |
| CLD-03 | Use `esp-aws-iot` (coreMQTT plus the Device Shadow library, and the Jobs library for v1.1 OTA). |
| CLD-04 | Keep-alive 60 s. Reconnect back-off 1 s → 5 min with jitter. |
| CLD-05 | Sync time with SNTP before TLS, and every 6 h after that. Timestamps are UTC epoch ms. |
| CLD-06 | Offline buffer of 144 records (24 h) in RAM, replayed in order after reconnecting. |
| CLD-07 | QoS 1 publishes. JSON payloads ≤ 512 B. |

---

## 8. Cloud Requirements — Two Stacks

| Stack | Repo | Role |
|---|---|---|
| **`SaltMon-<env>`** (producer) | this repo, `cloud/` | The device side of AWS IoT Core. It registers devices, applies the policy, ingests and validates readings, and keeps the system-of-record history. It computes the forecast and detects offline devices. It **publishes normalized records** on an SNS topic. |
| **`ChoreCore-<env>`** (consumer) | `~/github/chorecore` (new feature) | Subscribes to the SaltMon topic, maps devices to a family, creates the "Add salt" and "Check salt monitor" chores, and shows the level in the UI. It does not need to know about MQTT, certificates, or IoT. |

Both stacks live in account `345482189436` (profile `sandbox26`), region **us-east-1**. The environment is `dev` unless stated otherwise. The only coupling is the **integration contract** (§8.3): one SNS topic ARN, published in SSM Parameter Store, plus a message schema. There are no CloudFormation exports, so either stack can be updated or redeployed on its own.

```
 ESP32 ──MQTT/TLS──► IoT Core ──rule──► λ saltmon-ingest ──► DDB SaltMon-<env>-readings
                                           │ (validate, dedupe)
                                           ▼
 λ saltmon-forecast (hourly) ──────► SNS SaltMon-<env>-readings ──► SQS (+DLQ) ──► ChoreCore λ softener
 λ saltmon-watchdog (15 min) ──────►     (kind = telemetry | event |                  ├─► table (SALTREAD#, SOFTENER#)
                                          forecast | status)                          ├─► "Add salt" chore ─► reminders
                                                                                      └─► GET /softener ─► UI
```

### 8.1 Device ↔ IoT Interface (MQTT)

| Direction | Topic | Payload |
|---|---|---|
| Device → cloud | `dt/saltmon/{thing}/telemetry` | Every burst (below) |
| Device → cloud | `dt/saltmon/{thing}/event` | `boot`, `state_change`, `refill_detected`, `bridge_suspected`, `sensor_fault` |
| Both | `$aws/things/{thing}/shadow/name/config/#` | Config shadow (§8.5) |
| Cloud → device (v1.1) | `$aws/things/{thing}/jobs/#` | OTA |

Telemetry (schema v1):

```json
{ "schema":1, "thing":"saltmon-a1b2c3", "ts":1790000000000, "seq":1234,
  "distance_mm":612, "distance_min_mm":598, "distance_max_mm":640, "valid":14, "samples":15,
  "level_pct":62.5, "state":"OK", "bridge_suspected":false,
  "temp_c":18, "rssi_dbm":-61, "uptime_s":86400, "fw":"0.1.0" }
```

`state` ∈ `OK | REFILL | FAULT | OBSTRUCTED | UNCALIBRATED`

Event: `{ "schema":1, "thing", "ts", "seq", "type", "from", "to", "detail" }`. The `boot` event adds `reset_reason` and `fw`.

The device knows nothing about families or ChoreCore.

### 8.2 SaltMon Stack Requirements (this repo, `cloud/`)

| ID | Requirement |
|---|---|
| IOT-01 | **IaC:** AWS CDK v2 in TypeScript (matching ChoreCore) under `cloud/`. Lambdas are Python 3.13 on arm64 with Powertools (logger, metrics, tracer). cdk-nag `AwsSolutionsChecks` is on. Everything is tagged `Project=SaltMon`. Stack name `SaltMon-<env>`, deployed with `cloud/deploy.sh <env>` (`AWS_PROFILE=sandbox26 AWS_REGION=us-east-1`). |
| IOT-02 | **Registry:** thing type `SaltMonitor`, and one IoT policy `SaltMon-<env>-device` scoped by policy variables. `iot:Connect` only with client ID `${iot:Connection.Thing.ThingName}`, and only if the thing is attached (`iot:Connection.Thing.IsAttached`). Publish only to `dt/saltmon/${iot:Connection.Thing.ThingName}/*`. Access only its own `config` shadow and jobs topics. Things and certificates are created by the provisioning tool (§8.4), not by CDK. |
| IOT-03 | **Ingest:** topic rule `saltmon_<env>_ingest`: `SELECT *, topic(3) AS thing_topic, topic(4) AS kind, timestamp() AS received_at FROM 'dt/saltmon/+/+'` → Lambda `saltmon-ingest`. Error action to a CloudWatch Logs group. |
| IOT-04 | **`saltmon-ingest`** does four things: <br>• Rejects records where `thing` ≠ `thing_topic` or `schema` is unknown (logs and counts them). <br>• Clamps and validates fields. <br>• Writes the record **conditionally** (`attribute_not_exists`), so duplicates from QoS 1 or the offline replay are dropped. <br>• Publishes **only newly stored** records to the SNS topic as §8.3 envelopes. |
| IOT-05 | **Readings table** `SaltMon-<env>-readings`: PK `thing`, SK `<kind>#<ts>` (`T#`, `E#`, `F#`, `S#`), plus an item `STATE` holding lastSeen, last level/state, fw, and online flag. On-demand billing, PITR on, **`RemovalPolicy.RETAIN`**, deletion protection on, TTL of 2 years on T#/E#/F#. |
| IOT-06 | **`saltmon-forecast`** (EventBridge Scheduler, hourly): per thing, take the hourly medians of the last 14 days. Cut the series at the last refill (a rise of ≥ 20 points). Fit a least-squares line on ≥ 48 h of data and compute: <br>• consumption rate (in/day, and lb/day at 10.3 lb/in — GEO-05) <br>• `refill_eta` (when the line crosses `refill_pct`) <br>• `days_to_refill` <br>• a confidence score (R² and sample count). <br>Store the result as `F#` and publish `kind=forecast`. If there is too little history, publish `confidence:"insufficient"` and no ETA. |
| IOT-07 | **`saltmon-watchdog`** (every 15 min): if no telemetry for > **1 h**, mark the thing offline and publish `kind=status {online:false, last_seen}`. On the next record, `saltmon-ingest` publishes `online:true`. Only transitions are published. |
| IOT-08 | **Topic** `SaltMon-<env>-readings`: standard SNS, SSE with a customer-managed KMS key whose key policy allows the SaltMon Lambdas to publish and SNS to deliver to subscriber queues in this account. The topic policy allows `sns:Subscribe` only from account `345482189436`. Its ARN is published to **SSM `/saltmon/<env>/readings-topic-arn`**, and the schema version to `/saltmon/<env>/contract-version`. |
| IOT-09 | **Config tool** `tools/saltmon-config.py`: shows the shadow, sets `desired` keys (§8.5), and runs "calibrate full/low from the latest reading". This is the only v1 remote-config path. ChoreCore is read-only toward the device in v1. |
| IOT-10 | **Observability:** Powertools metrics `Ingested`, `Duplicate`, `Rejected`, `PublishFailed`. The rule error log group, and all Lambda logs, are kept for 30 days. |
| IOT-11 | **Security:** no AWS credentials on the device. Each Lambda role is least-privilege: the table, `sns:Publish` on this topic only, and KMS on this key only. No public endpoints. |
| IOT-12 | **Tests:** pytest with moto for ingest (validation, dedupe, publish only when new), forecast (synthetic consumption series, refill cut, insufficient data), and watchdog transitions. CDK Jest assertions cover the policy document, rule SQL, and RETAIN/PITR. |
| IOT-13 | **Cost:** 1 device, about 150 messages/day, hourly forecast: **< $1/month**. |
| IOT-14 | **Deploy safety:** `cdk diff` is reviewed before every deploy, and I **ask before running `cdk deploy`**. No stateful resource is ever replaced. `cdk destroy` leaves the table and KMS key (RETAIN). |

### 8.3 Integration Contract (SaltMon → consumers)

Every SNS message has message attributes `kind` (String) and `thing` (String), so subscribers can use filter policies. The body is:

```json
{ "contract": 1, "kind": "telemetry|event|forecast|status",
  "thing": "saltmon-a1b2c3", "ts": 1790000000000, "received_at": 1790000000321,
  "data": { ... } }
```

| `kind` | `data` |
|---|---|
| `telemetry` | The device telemetry fields (§8.1) |
| `event` | The device event fields (§8.1) |
| `forecast` | `level_pct, rate_in_per_day, rate_lb_per_day, refill_eta (epoch ms or null), days_to_refill (or null), confidence ("high"\|"low"\|"insufficient"), r2, points` |
| `status` | `online (bool), last_seen` |

Rules:
- Delivery is **at least once** and not ordered. Consumers de-duplicate on (`thing`, `kind`, `ts`).
- Fields are only ever added. A breaking change bumps `contract` and is published side by side on a new topic.
- The contract doc lives at `docs/integration-contract.md`. ChoreCore's intent links to it.

### 8.4 Provisioning Tool (`tools/provision.py`)

| ID | Requirement |
|---|---|
| PRV-01 | Inputs: serial port and env (`dev` by default). It runs with `AWS_PROFILE=sandbox26 AWS_REGION=us-east-1`. It reads the device MAC with `esptool` and derives the thing name `saltmon-<mac3>`. |
| PRV-02 | Steps: <br>1. Create the thing (type `SaltMonitor`). <br>2. `CreateKeysAndCertificate`. <br>3. Attach policy `SaltMon-<env>-device`. <br>4. Attach the cert to the thing. <br>5. Build the `esp_secure_cert` partition (cert, key, Amazon Root CA 1) and a factory NVS partition (ATS endpoint, thing name). <br>6. Flash both. |
| PRV-03 | Idempotent: an existing thing is reused, and a new cert is issued only with `--rotate`. Keys live only in git-ignored `tools/out/` and are wiped after a verified flash, unless `--keep`. |
| PRV-04 | `--dry-run` prints every AWS call without making it. `--revoke` sets the cert INACTIVE and never deletes anything. Deleting a thing or cert needs a separate command plus a typed confirmation. |

### 8.5 Device Shadow `config`

| Key | Default | Range |
|---|---|---|
| `d_full_mm` | 150 | 50–1100 |
| `d_low_mm` | 900 | 100–1100, > `d_full_mm` |
| `refill_pct` | 15 | 5–50 |
| `sample_interval_s` | 600 | 60–3600 |
| `led_dim` | 20 | 1–255 |
| `bridge_days` | 14 | 0–60 (0 = off) |

The device validates each `desired` value, applies it, stores it in NVS, and writes it back to `reported`. It rejects invalid values and returns an error field.

### 8.6 Device Security

| ID | Requirement |
|---|---|
| SEC-01 | Wi-Fi setup via ESP-IDF BLE provisioning (ESP BLE Provisioning app), security scheme 1 or 2. The proof-of-possession code is on a label inside the enclosure. |
| SEC-02 | The certificate and key live in `esp_secure_cert`, written by the provisioning tool (§8.4). They never appear in the firmware image or in git (`.gitignore` covers `*.pem`, `*.key`, `tools/out/`). |
| SEC-03 | NVS encryption is on, using the C6's HMAC-based scheme. |
| SEC-04 | Flash encryption and Secure Boot v2 are an optional release step only (they burn eFuses irreversibly). |
| SEC-05 | TLS or authentication failures never cause a boot loop. The status LED shows Red 4 Hz, and the device retries with back-off. |

### 8.7 ChoreCore Consumer Feature (requirements handed to ChoreCore)

To be written up as an AI-DLC intent in ChoreCore and implemented there, following its AGENTS.md (invariants INV-01…06, the config-driven Lambdas, and tests). Listed here so both sides agree on the contract.

| ID | Requirement |
|---|---|
| CC-01 | **Subscribe:** an SQS queue `ChoreCore-<env>-saltmon` (SSE-SQS, with a DLQ after 5 receives) subscribed to the topic from SSM `/saltmon/<env>/readings-topic-arn`, with raw delivery. The queue triggers Lambda `softener` in batches with partial-batch failure reporting. A new construct `saltmon-consumer-construct.ts`, plus a config block in all four `app-config.*.json`. |
| CC-02 | **Device→family map:** an admin-managed record `SOFTENER#<thing>` under `family_pk()`, seeded from config `saltmon.devices: {"saltmon-xxxxxx": "ct_harman"}`. Messages for unmapped things are logged and dropped. |
| CC-03 | **Store:** `SALTREAD#<thing>#<ts>` records (`ttl` of 1 year) and the latest level, state, forecast and online flag on `SOFTENER#<thing>`. Idempotent on (thing, kind, ts). Numbers stored as `Decimal`. |
| CC-04 | **"Add salt" chore (forecast-driven):** when a `forecast` message has `days_to_refill` ≤ **`lead_days` (default 3)**, confidence ≠ `insufficient`, and there is no open task, create a `due_by` task "Add salt to water softener" (list "Softener", **assigned to Jeff Harman** by Cognito sub from config, `dueAt = refill_eta`, back-reference `softenerAction`). If the task is already open, update its `dueAt` when the ETA moves by more than 12 h. **Fallback:** if a telemetry `state=REFILL` arrives with no open task, create the task due now. Delivery uses the existing `reminders`. |
| CC-05 | **Never auto-complete (INV-01):** `refill_detected` only annotates the open task and enables **Mark done** in the UI. A human completing the task records a refill on `SOFTENER#<thing>`. |
| CC-06 | **"Check salt monitor" chore:** created when `status.online=false` persists for > 1 h after the message (2 h total), or on FAULT/OBSTRUCTED telemetry lasting > 1 h. Assigned to Jeff, one open at a time, never auto-completed. |
| CC-07 | **API and UI:** `GET /softener` and `GET /softener/{thing}/readings`, both Cognito-authorized and family-scoped. `Softener.tsx` shows a level gauge (% and ≈ lb), a 30/90-day chart, days to refill with a confidence note, online/last seen, and a link to the open chore. It is the toggleable section `softener`. It is read-only toward the device in v1. |
| CC-08 | **Tests:** pytest with moto (SQS event → store, chore create/update/no duplicate, unmapped thing, INV-01), CDK Jest, and Vitest. |
| CC-09 | **Deploy order:** SaltMon first, then ChoreCore. The ChoreCore stack reads the SSM parameter at deploy time, so it has no hard CloudFormation dependency. |

---

## 9. Enclosure & Mechanical Requirements

Enclosure: the user's unlabeled ABS gasketed junction box. Measured 2026-09-28 (user sketch):

| Dimension | inch | mm |
|---|---|---|
| Outside L × W | 4½ × 3½ | 114.3 × 88.9 |
| **Inside depth, base** (floor to rim) | 1¾ | 44.5 |
| **Inside depth, lid** | ½ | 12.7 |
| Total inside depth, lid closed | 2¼ | 57.2 |
| Wall thickness | ⅛ | 3.2 |
| **Inside L × W** | **4¼ × 3¼** | **108.0 × 82.6** |
| Corner pillars (each corner, inside) | ¾ across the width × ½ along the length | 19.1 × 12.7 |
| Gap between pillars, across the short wall | 1¾ | 44.5 |
| Gap between pillars, along the long wall | 3¼ | 82.6 |

```
      Carrier outline, inside view (portrait, lid toward viewer), mm
      ┌──┐◄──────────── 82.6 inside ────────────►┌──┐
      │P │                                      │ P│  P = pillar 19.1 × 12.7
      └──┘──────────────────────────────────────└──┘
         │      U2 · J_PANEL · RN1 · R1–R8      │
         │  side   ┌── kit antenna ──┐   side   │   board 92 × 80.5
         │  zone   │  keep-out 15 mm │   zone   │   (bottom tab 14 × 39.5)
         │ (F1, D1,│                 │ (R, C,   │
         │  C1)    │   ESP32-C6 kit  │  J_SNS,  │
      ┌──┐──────┐  │   25.4 × 48.3   │ ┌J_SPARE)└──┐
      │P │      │  └────┤USB├────────┘J1│     │ P│
      └──┘      └───────────────────────┘     └──┘
                ▲ bottom wall: USB-C cut-out + DC jack hole
```

| ID | Requirement |
|---|---|
| MEC-01 | The box is wall-mounted in portrait with the lid facing out (lid = front panel, §5.3). The **bottom wall** (the short wall) carries the DC jack hole and the USB-C cut-out, which exposes the UART port. The **sensor ribbon** leaves through a grommet or slot in the side wall just above the lower pillar, with a drip loop and strain relief (a cable tie through two holes in the carrier). |
| MEC-02 | **Carrier outline 92.0 × 80.5 mm: a full-width body with one 14.0 × 39.5 mm tab at the bottom end** (14.0 × 20.5 mm notches at the two bottom corners, ≈ 1 mm clearance to walls and pillars). The tab fits between the bottom pillars with 2.5 mm clearance per side. The top edge is straight and sits just below the top pillars; the top tab of rev 0.1 held no parts and was removed in rev 0.2. |
| MEC-03 | The bottom tab holds the dev kit (USB end flush with the tab edge, 1 mm from the wall) and J1 beside it. That is 25.4 + 9 mm plus gaps, about 37.5 of the 39.5 mm available. The **antenna end points into the box center**. The antenna keep-out (MCU-02) goes there: a ~26 × 15 mm routed slot under the antenna overhang, and no copper within 15 mm. The full-width body holds U2, the resistors, J_PANEL, J_SNS, F1, D1, and C1. |
| MEC-04 | Stack height from the floor: standoffs 6 mm → carrier 1.6 mm (top at 7.6) → female headers 8.5 mm → kit PCB (top at 17.7) → **USB-C centered about 19.3 mm above the floor**. **DC jack (PJ-102AH) axis about 14.1 mm above the floor.** The tallest carrier part is C1 (8 × 11.5 mm, top at 19.1). Tallest overall is the kit and module at about 21 mm, which leaves about 23 mm in the base plus 12.7 mm in the lid for the lid-mounted parts (the push-button body is ≤ 20 mm deep). The USB-C cut-out is 13 × 8 mm (clears a plug overmold through the 3.2 mm wall), and the jack hole is Ø8 mm. |
| MEC-05 | Mounting: 4 × M3 holes in the full-width region, just inside the notches. The carrier sits on 6 mm nylon standoffs, screwed to the molded floor bosses if they line up, otherwise through M3 holes drilled in the floor with sealing washers. |
| MEC-06 | Lid parts stay inside the gasket line and clear of the four pillar screws. The 1:1 **drilling template** is the User.Drawings layer of `kicad/LidPanel/LidPanel.kicad_pcb` (export command in `kicad/LidPanel/gen_pcb.py`). Print it at 100 %, check the 50 mm bar, and tape it to the outside of the lid. After drilling, seal the switch and button with their own nuts or gaskets and run a bead of silicone around each LED flange on the inside. |
| MEC-07 | The box is mounted through its 4 corner screw holes. There are no wall screws through the base floor in the board area, and the carrier has no screw keep-clear zones. |
| MEC-08 | Carrier and lid PCBs: 2-layer, 1.6 mm, 1 oz copper, all through-hole. GND pour everywhere except the carrier's antenna keep-out. Both pass KiCad ERC and DRC with zero errors. |
| MEC-09 | Lid board mounting: 4 × M3 nylon standoffs, about 10 mm, between the lid and the board front. Fix them to the lid with M3 screws and sealing washers through the template's Ø3.2 holes, or bond them on (no holes). Assembly: (1) mount the bare board; (2) each LED sits on a nylon LED spacer the same length as the standoffs, which pushes its flange against the lid; (3) solder and trim the leads. Parts: `docs/lid-pick-list.md`. J_LID hangs about 9 mm behind the board (bottom about 36 mm above the floor with the lid closed), which clears the carrier and the kit. |

---

## 10. Verification Plan

| Test | Pass | Covers |
|---|---|---|
| −5 V at the jack | No V_SYS, no damage | PWR-03 |
| Short V_SYS | F1 trips and recovers | PWR-04 |
| Unplug the lid ribbon | Device off, nothing damaged | PWR-05 |
| USB only with SW1 off; USB and jack together | Runs; no backfeed | PWR-06 |
| Reset / flash | Only the White LED is lit | LED-02/04 |
| LED currents | Within ±25% of §5.1 | LED-01 |
| 1.2 m sensor ribbon: 1000 bursts | ≥ 99.9% valid frames | SNS-02/03 |
| Bench: 10 / 30 / 60 / 100 cm onto salt in a bucket | Median within ±1.5 cm | FW-10 |
| In the tank, full and near-empty | No echoes from the brine chamber (min ≈ median) | GEO-02 |
| Lift the lid for 5 min during a refill | No fault alert; refill detected afterwards | FW-14/17 |
| First boot with no credentials | BLE provisioning works | SEC-01 |
| Normal run | A `T#` item every 10 min, an SNS message, and a ChoreCore `SALTREAD#` record; the Softener page updates | IOT-04/05, CC-03/07 |
| Publish to another thing's topic | Denied by the policy | IOT-02 |
| Replay the same record twice | Stored once and published once | IOT-04 |
| Feed the forecast a synthetic 1 in/day decline | ETA correct to ±0.5 day; `insufficient` with < 48 h of data | IOT-06 |
| Forecast reports ≤ 3 days | One "Add salt" chore due at the ETA; reminders fire; no duplicate | CC-04 |
| Force REFILL (shadow `d_low_mm` = current distance − 10 mm) with no chore open | Fallback chore due now | CC-04 |
| Refill the tank with the chore open | Chore annotated, **not** completed; the Mark done button works | CC-05 |
| Power off for 2.5 h | `status` offline message, then one "Check salt monitor" chore; online again after power returns | IOT-07, CC-06 |
| Send a message to the ChoreCore queue that fails to process | Lands in the DLQ after 5 receives | CC-01 |
| Router off for 2 h | Buffered records replayed in order | CLD-06 |
| Revoke the certificate | Red 4 Hz, no reboot loop | SEC-05 |
| 14 days of real data | Forecast within ±3 days of the actual refill date | IOT-06 |
| `cloud` tests, and `make test-all` in ChoreCore | Pass | IOT-12, CC-08 |
| `provision.py --dry-run`, then a real run | Thing, cert and policy created; device connects on the first boot | PRV-01…04 |

---

## 11. Out of Scope (v1)

Battery operation, controlling the softener, and reading data from the Culligan Accusoft board. OTA updates are planned for **v1.1**. Remote config from the ChoreCore UI (v1 uses `tools/saltmon-config.py`).

---

## 12. Open Questions

| # | Question | Default |
|---|---|---|
| — | *All questions resolved as of v0.8.* The floor-boss positions are not used: standoffs go through M3 holes drilled in the floor (MEC-05). | |
