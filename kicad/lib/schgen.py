"""Shared helpers for the label-driven schematic generators (carrier and lid panel).

Every pin end gets a net label (or a no-connect flag), so each generator's netlist is defined entirely by the
`place(...)` calls it makes. Symbols are embedded from the stock KiCad libraries and kicad/lib/SaltMon.kicad_sym.

Usage: call init(...) once, then place()/note()/text(), then write(...).
"""
import math
import re
import uuid
from pathlib import Path

STOCK = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")
LOCAL = {"SaltMon": Path(__file__).resolve().parent / "SaltMon.kicad_sym"}
G = 2.54

_cfg = {}

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


_seq = [0]


def u(key=None):
    """Deterministic UUIDs, so regenerating keeps the PCB's links to the symbols (and diffs small)."""
    if key is None:
        _seq[0] += 1
        key = f"item{_seq[0]}"
    return str(uuid.uuid5(_cfg["ns"], key))


def init(project, root_uuid, ns):
    """project: KiCad project name; root_uuid: the sheet UUID; ns: UUID namespace (one per board)."""
    _cfg.update(project=project, root=root_uuid, ns=uuid.UUID(ns))


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
        f'\t\t(instances (project "{_cfg["project"]}" (path "/{_cfg["root"]}" (reference "{ref}") (unit 1)))))')
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


# ---------------------------------------------------------------- write


def write(out, title, date, rev, comments, paper="A3"):
    lib_syms = "\n\t\t".join(dump(s, 3) for s in used.values())
    cmt = "".join(f'\n\t\t(comment {i + 1} "{c}")' for i, c in enumerate(comments))
    out.write_text(
        "(kicad_sch\n\t(version 20260306)\n\t(generator \"eeschema\")\n\t(generator_version \"10.0\")\n"
        f'\t(uuid "{_cfg["root"]}")\n\t(paper "{paper}")\n'
        f'\t(title_block (title "{title}") (date "{date}") (rev "{rev}"){cmt})\n'
        f"\t(lib_symbols\n\t\t{lib_syms})\n\t" + "\n\t".join(items) +
        '\n\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n')
    print("wrote", out)
