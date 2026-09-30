# SaltMon Pick List — lid panel rev 0.1

Everything for the lid panel board and its cable, for one build. Refs match `kicad/LidPanel/LidPanel.kicad_sch`;
specs come from `docs/requirements.md` §3.2, §3.3, §5.3, MEC-06 and MEC-09. The carrier and the rest of the build
are in [pick-list.md](pick-list.md). Everything is through-hole. **Have** = the part is already on hand.
DigiKey numbers were checked on 2026-09-30; stock and prices change.

## 1. Board and LEDs

| ✓ | Qty | Part | Refs | Notes |
|---|---|---|---|---|
| ☐ | 1 | Lid panel PCB, 50 × 63 mm, 2-layer, 1.6 mm | | Gerbers from `kicad/LidPanel` |
| **Have** | 1 | 5 mm flat-top LED, green | D1 FULL | |
| **Have** | 1 | 5 mm flat-top LED, yellow | D2 MID | |
| **Have** | 1 | 5 mm flat-top LED, orange | D3 LOW | |
| **Have** | 1 | 5 mm flat-top LED, red | D4 REFILL | |
| **Have** | 1 | 5 mm flat-top LED, blue | D5 DATA | |
| **Have** | 1 | 5 mm flat-top LED, purple | D6 SENS | |
| **Have** | 1 | 5 mm flat-top LED, bi-color red/green, **common cathode**, 3-lead | D7 NET | The board expects pin order R / K / G: check the part |
| **Have** | 1 | 5 mm flat-top LED, white | D8 PWR | |

## 2. LED housings (spacers)

| ✓ | Qty | Part | Refs | DigiKey | Notes |
|---|---|---|---|---|---|
| ☐ | 7 | 5 mm (T-1¾) LED spacer, nylon, **2-lead**, 10 mm long | D1–D6, D8 | [NTM-400-ND](https://www.digikey.com/en/products/result?keywords=NTM-400) (Bivar NTM-400) | 10.16 mm long, Ø5.1 mm. Fits over the leads between the board and the LED flange |
| ☐ | 1 | 5 mm LED spacer, **3-lead**, 10 mm long | D7 | [492-1104-ND](https://www.digikey.com/en/products/detail/bivar-inc/ELM-3-400/3089297) (Bivar ELM 3-400) | 10.16 mm, PVC. Cross slots plus a center hole, sold as a 3-lead 5 mm spacer: check the fit. If it doesn't fit, use a 10 mm jig while soldering: the 3 leads hold D7 steady |

**The spacer length must equal the standoff length (§4).** Together they set the gap between the board and the
lid, so each flange is pressed against the lid. Spacers are often sold in inch lengths (0.375" = 9.5 mm,
0.400" = 10.2 mm). If yours differ from 10 mm, buy standoffs of the same length. The listed 10.16 mm spacers with
10 mm standoffs give 0.16 mm of preload on each flange, which is fine.

## 3. Connector, switch and button

| ✓ | Qty | Part | Refs | DigiKey | Notes |
|---|---|---|---|---|---|
| ☐ | 1 | 2×8 shrouded (keyed) box header, 2.54 mm, **right-angle** | J1 (J_LID) | [732-2099-ND](https://www.digikey.com/en/products/detail/würth-elektronik/61201621721/2060595) (Würth 61201621721) | Fitted on the back of the board |
| **Have** | 1 | SPDT mini slide switch, panel mount, 2 A / 125 V AC | SW1 (pads J2) | | Uses the common pin and one throw |
| ☐ | 1 | Momentary push-button, normally open, panel mount, M7 bushing | SW2 (pads J3) | [EG2011-ND](https://www.digikey.com/en/products/detail/e-switch/PS1024ABLK/44576) (E-Switch PS1024ABLK) | Ø7.2 mm hole, about 15 mm behind the lid, solder lugs. Red cap: PS1024ARED |

## 4. Mounting (MEC-09)

| ✓ | Qty | Part | Refs | DigiKey | Notes |
|---|---|---|---|---|---|
| ☐ | 4 | M3 × 10 mm nylon standoffs, female–female | H1–H4 | [36-25510-ND](https://www.digikey.com/en/products/detail/keystone-electronics/25510/1532188) (Keystone 25510) | Same length as the LED spacers |
| ☐ | 4 | M3 × 6 mm screws, nylon | H1–H4 | [732-13704-ND](https://www.digikey.com/en/products/detail/würth-elektronik/97790603111/10056387) (Würth 97790603111) | Board side |
| ☐ | 4 | M3 × 8 mm self-sealing screws, stainless | | [335-1149-ND](https://www.digikey.com/en/products/detail/apm-hexseal/RM3X8MM-2701/3712297) (APM Hexseal RM3X8MM 2701) | Lid side, through the template's Ø3.2 holes. An O-ring under the head seals the hole, so no washer is needed. Check the lid thickness: 8 mm suits a lid up to about 3 mm thick |
| ☐ | — | Or: epoxy / cyanoacrylate | | | Bond the standoffs to the lid instead, so there are no screw holes |

## 5. Lid cable

| ✓ | Qty | Part | DigiKey | Notes |
|---|---|---|---|---|
| ☐ | 1 ft | 16-way 0.05" (1.27 mm) flat ribbon, 28 AWG | [3M 3365/16, per foot](https://www.digikey.com/en/products/detail/3m/3365-16/22532519) | About 20 cm plus trim |
| ☐ | 2 | 2×8 IDC ribbon socket, 2.54 mm | [609-1740-ND](https://www.digikey.com/en/products/detail/amphenol-icc-fci/71600-016LF/1002055) (Amphenol 71600-016LF) | One at each end, crimped 1:1 with the pin-1 stripe at pin 1 of both sockets. Or 3M 89116-0101 |
| ☐ | — | Or: a ready-made 2×8 IDC cable, 12" (305 mm) | [1528-2944-ND](https://www.digikey.com/en/products/result?keywords=1528-2944-ND) (Adafruit 4170) | Replaces the two rows above. Longer than needed; check stock (it had a lead time) |

## 6. Consumables

| ✓ | Part | Use |
|---|---|---|
| ☐ | Hookup wire (24–26 AWG), ~20 cm, + small heat-shrink | SW1 → J2, SW2 → J3 |
| ☐ | Neutral-cure silicone | A bead around each LED flange inside the lid (MEC-06) |
| ☐ | Glue or ribbon clamp | Cable strain relief at the lid |

## Tools

- 5 mm drill (LED holes), 3.2 mm drill (standoff screws), a 7.2 mm or 9/32" drill (PS1024 push-button; a step drill for others) and a file (switch slot).
- IDC ribbon crimp tool or a small vise.
- The printed drilling template: `kicad-cli pcb export pdf --mode-single -l User.Drawings --scale 1 -o lid-template.pdf kicad/LidPanel/LidPanel.kicad_pcb`.
  Print at 100 % and check the 50 mm bar.

## Assembly Order

1. Drill the lid from the template. Mount SW1 and SW2 in the lid.
2. Fit J1 and solder it. Put a spacer over the leads of each LED, then set the LEDs in the board, but don't solder them yet.
3. Screw the board to the standoffs, and the standoffs to the lid. Each LED passes through its hole, and the spacer
   pushes its flange against the lid. Solder and trim the LED leads from the back.
4. Wire SW1 to J2 and SW2 to J3. Seal the LED flanges with silicone. Plug in the ribbon.
