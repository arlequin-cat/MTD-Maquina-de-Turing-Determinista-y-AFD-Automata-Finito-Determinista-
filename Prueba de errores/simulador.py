from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class DefinitionError(Exception):
    pass


# ─── Estructuras ──────────────────────────────────────────────

@dataclass
class AFD:
    start: str
    accept: Set[str]
    transitions: Dict[Tuple[str, str], str]


@dataclass
class MTD:
    start: str
    blank: str
    transitions: Dict[Tuple[str, str], Tuple[str, str, str]]
    breakpoints: Set[Tuple[str, str]] = field(default_factory=set)


# ─── Parser ───────────────────────────────────────────────────

def _is_row_number_column(rows: List[List[str]]) -> bool:
    """
    Devuelve True SOLO si la primera columna forma una secuencia
    estrictamente consecutiva 1,2,3,... (o 01,02,03,...).
    Asi se distinguen numeros de fila de estados llamados 0,1,2...
    """
    try:
        nums = [int(r[0]) for r in rows]
    except ValueError:
        return False
    return nums == list(range(1, len(nums) + 1))


def parse_file(path: str):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    meta: Dict[str, str] = {}
    rows: List[dict] = []

    for raw in lines:
        line = raw.split(";")[0].split("#")[0].strip()
        if not line:
            continue
        breakpoint_flag = line.endswith("!")
        if breakpoint_flag:
            line = line[:-1].strip()
        if ":" in line:
            k, _, v = line.partition(":")
            if " " not in k.strip():   # solo meta si la clave es una sola palabra
                meta[k.strip().lower()] = v.strip()
                continue
            parts = line.split()
            if parts:
                rows.append({"parts": parts, "bp": breakpoint_flag})
        else:
            parts = line.split()
            if parts:
                rows.append({"parts": parts, "bp": breakpoint_flag})

    if not rows:
        raise DefinitionError("No se encontraron transiciones.")

    # Quitar numero de fila solo si es secuencia 1,2,3,...
    if _is_row_number_column([r["parts"] for r in rows]):
        for r in rows:
            r["parts"] = r["parts"][1:]

    widths = {len(r["parts"]) for r in rows}
    if len(widths) != 1:
        raise DefinitionError(
            f"Columnas inconsistentes en las transiciones: {widths}. "
            "Se esperan 3 (AFD) o 5 (MTD)."
        )

    width = widths.pop()
    if width == 3:
        return _build_afd(meta, rows)
    if width == 5:
        return _build_mtd(meta, rows)
    raise DefinitionError(
        f"Las transiciones tienen {width} columna(s). "
        "Se esperan 3 (AFD) o 5 (MTD)."
    )


def _build_afd(meta, rows):
    transitions: Dict[Tuple[str, str], str] = {}
    for r in rows:
        state, symbol, nxt = r["parts"]
        key = (state, symbol)
        if key in transitions:
            raise DefinitionError(f"Transicion duplicada AFD: ({state}, {symbol})")
        transitions[key] = nxt

    start = meta.get("start") or meta.get("inicial") or rows[0]["parts"][0]
    accept_raw = (meta.get("accept") or meta.get("aceptacion")
                  or meta.get("final") or "")
    accept = {s.strip() for s in accept_raw.split(",") if s.strip()}
    if not accept:
        raise DefinitionError("Indique estados de aceptacion: 'accept: q1,q2'")
    return "AFD", AFD(start=start, accept=accept, transitions=transitions)


def _build_mtd(meta, rows):
    transitions: Dict[Tuple[str, str], Tuple[str, str, str]] = {}
    breakpoints: Set[Tuple[str, str]] = set()

    for r in rows:
        state, read, write, move, nxt = r["parts"]
        key = (state, read)
        if key in transitions:
            raise DefinitionError(f"Transicion duplicada MTD: ({state}, {read})")
        move = move.lower()
        if move not in {"l", "r", "*"}:
            raise DefinitionError(f"Movimiento invalido '{move}'. Use l, r o *.")
        transitions[key] = (write, move, nxt)
        if r["bp"]:
            breakpoints.add(key)

    start = meta.get("start") or meta.get("inicial") or rows[0]["parts"][0]
    blank = meta.get("blank") or meta.get("blanco") or "_"
    return "MTD", MTD(start=start, blank=blank,
                      transitions=transitions, breakpoints=breakpoints)


# ─── Entradas ─────────────────────────────────────────────────

def read_inputs(path: str) -> List[str]:
    inputs = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith(("#", ";")):
            continue
        inputs.append(raw.rstrip("\n"))   # conserva espacios, solo quita salto de linea
    return inputs


# ─── Parse de cinta (soporte de * como posicion inicial) ────────

def parse_tape(word: str) -> Tuple[dict, int]:
    """
    Si la cinta contiene '*', ese caracter marca la posicion inicial
    de la cabeza (igual que el simulador morphet). El '*' se elimina
    del contenido de la cinta.
    Ejemplos:
      '1____*'  -> cinta='1____', cabeza=5
      '*_111'   -> cinta='_111',  cabeza=0
      '11'      -> cinta='11',    cabeza=0  (sin * = cabeza en 0)
    """
    if "*" in word:
        head = word.index("*")
        word = word[:head] + word[head + 1:]   # quita el *
    else:
        head = 0
    tape = {i: ch for i, ch in enumerate(word.replace(" ", "_"))}
    return tape, head


# ─── Visualizacion de cinta ───────────────────────────────────

WINDOW = 10   # celdas a cada lado de la cabeza

def _tape_display(tape: dict, blank: str, head: int) -> str:
    cells = []
    for i in range(head - WINDOW, head + WINDOW + 1):
        sym = tape.get(i, blank)
        cells.append(f"[{sym}]" if i == head else f" {sym} ")
    return "".join(cells)


def _tape_arrow(head: int) -> str:
    pos = WINDOW   # la cabeza siempre esta en el centro de la ventana
    spaces = pos * 3 + 1
    return " " * spaces + "^"


def _tape_raw(tape: dict, blank: str) -> str:
    used = [i for i, v in tape.items() if v != blank]
    if not used:
        return blank
    lo, hi = min(used), max(used)
    return "".join(tape.get(i, blank) for i in range(lo, hi + 1))


# ─── Wildcard lookup ──────────────────────────────────────────

def _lookup(transitions, state, sym):
    for s, c in [(state, sym), (state, "*"), ("*", sym), ("*", "*")]:
        if (s, c) in transitions:
            write, move, nxt = transitions[(s, c)]
            write = sym   if write == "*" else write
            nxt   = state if nxt   == "*" else nxt
            return write, move, nxt, (s, c)
    return None


# ─── AFD runner ───────────────────────────────────────────────

def run_afd(machine: AFD, word: str, step_mode: bool, delay: float) -> dict:
    state = machine.start
    path  = [state]
    visual = step_mode or delay > 0
    SEP = "-" * 55

    if visual:
        print(f"\n  Cadena : '{word}'")
        print(f"  Inicio : {state}")
        print(SEP)

    for i, ch in enumerate(word):
        key = (state, ch)
        if key not in machine.transitions:
            if visual:
                print(f"  Paso {i+1:>3}: ({state}, '{ch}') -> sin transicion -> RECHAZA")
            return {"entrada": word, "aceptada": False,
                    "motivo": f"Sin transicion para ({state}, {ch})",
                    "estado_final": state, "recorrido": " -> ".join(path)}

        nxt = machine.transitions[key]
        if visual:
            print(f"  Paso {i+1:>3}: estado={state:<10} lee='{ch}'  ->  {nxt}")
            _wait(step_mode, delay)

        state = nxt
        path.append(state)

    ok = state in machine.accept
    if visual:
        print(f"\n  Fin: estado={state}  ->  {'ACEPTADA' if ok else 'RECHAZADA'}")
    return {"entrada": word, "aceptada": ok,
            "motivo": "Cadena aceptada" if ok else "Estado final no aceptador",
            "estado_final": state, "recorrido": " -> ".join(path)}


# ─── MTD runner ───────────────────────────────────────────────

def run_mtd(machine: MTD, word: str, max_steps: int,
            step_mode: bool, delay: float) -> dict:

    tape, head = parse_tape(word)
    state = machine.start
    blank = machine.blank
    seen  : set = set()
    visual = step_mode or delay > 0
    SEP   = "-" * (WINDOW * 2 * 3 + 10)

    def show_step(step: int, info: str = ""):
        print(f"\n  Paso {step:<5}  Estado: {state:<14}  Cabeza: {head}")
        print("  " + _tape_display(tape, blank, head))
        print("  " + _tape_arrow(head))
        if info:
            print(f"  {info}")
        print(SEP)

    if visual:
        print(f"\n  Entrada : '{word}'")
        print(f"  Inicio  : estado={state}   cabeza=0")
        print(SEP)
        show_step(0, "Estado inicial")
        _wait(step_mode, delay)

    for step in range(1, max_steps + 1):
        sym = tape.get(head, blank)

        snapshot = (state, head,
                    tuple(sorted((k, v) for k, v in tape.items() if v != blank)))
        if snapshot in seen:
            return {"entrada": word, "aceptada": False,
                    "motivo": "Ciclo detectado",
                    "estado_final": state, "pasos": step,
                    "cinta_final": _tape_raw(tape, blank)}
        seen.add(snapshot)

        if state.startswith("halt"):
            ok = "reject" not in state
            if visual:
                print(f"\n  Detenida en '{state}'  ->  {'ACEPTADA' if ok else 'RECHAZADA'}")
            return {"entrada": word, "aceptada": ok,
                    "motivo": f"Estado halt: {state}",
                    "estado_final": state, "pasos": step - 1,
                    "cinta_final": _tape_raw(tape, blank)}

        tr = _lookup(machine.transitions, state, sym)
        if tr is None:
            if visual:
                print(f"\n  Sin transicion para ({state}, '{sym}')  ->  RECHAZADA")
            return {"entrada": word, "aceptada": False,
                    "motivo": f"Sin transicion para ({state}, {sym})",
                    "estado_final": state, "pasos": step,
                    "cinta_final": _tape_raw(tape, blank)}

        write, move, nxt, key = tr
        info = f"({state}, '{sym}') -> escribe='{write}'  dir={move}  -> {nxt}"

        tape[head] = write
        if tape[head] == blank:
            tape.pop(head, None)
        if move == "r":
            head += 1
        elif move == "l":
            head -= 1
        state = nxt

        if visual:
            show_step(step, info)
            is_bp = key in machine.breakpoints
            if is_bp:
                print("  *** BREAKPOINT ***")
            if step_mode or is_bp:
                input("  [Enter para continuar]")
            else:
                time.sleep(delay)

    return {"entrada": word, "aceptada": False,
            "motivo": f"Limite de {max_steps} pasos alcanzado",
            "estado_final": state, "pasos": max_steps,
            "cinta_final": _tape_raw(tape, blank)}


def _wait(step_mode: bool, delay: float):
    if step_mode:
        input("  [Enter para continuar]")
    elif delay > 0:
        time.sleep(delay)


# ─── Salida ───────────────────────────────────────────────────

def execute(definition: str, inputs_file: str, max_steps: int,
            step_mode: bool, delay: float):

    mtype, machine = parse_file(definition)
    entries = read_inputs(inputs_file)
    visual  = step_mode or delay > 0
    SEP     = "=" * 65

    print(SEP)
    print(f"  Definicion : {definition}")
    print(f"  Tipo       : {mtype}  (detectado automaticamente)")
    if step_mode:
        print("  Modo       : PASO A PASO  (Enter para avanzar)")
    elif delay > 0:
        print(f"  Modo       : AUTOMATICO  (delay={delay}s por paso)")
    print(SEP)

    results = []
    for idx, entry in enumerate(entries, 1):
        print(f"\n{SEP}")
        print(f"  Entrada #{idx}: '{entry}'")
        print(SEP)

        if mtype == "AFD":
            r = run_afd(machine, entry, step_mode, delay)
        else:
            r = run_mtd(machine, entry, max_steps, step_mode, delay)
        results.append(r)

        if not visual:
            verdict = "ACEPTADA" if r["aceptada"] else "RECHAZADA"
            print(f"  Resultado   : {verdict}")
            print(f"  Motivo      : {r['motivo']}")
            print(f"  Estado final: {r['estado_final']}")
            if "recorrido" in r:
                print(f"  Recorrido   : {r['recorrido']}")
            if "pasos" in r:
                print(f"  Pasos       : {r['pasos']}")
            if "cinta_final" in r:
                print(f"  Cinta final : {r['cinta_final']}")

    print(f"\n{SEP}")
    ok = sum(1 for r in results if r["aceptada"])
    print(f"  RESUMEN: Total={len(results)}  "
          f"Aceptadas={ok}  Rechazadas={len(results)-ok}")
    print(SEP)


# ─── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Simulador MTD/AFD — detecta el tipo automaticamente."
    )
    parser.add_argument("definition", nargs="?", help="Archivo de la maquina")
    parser.add_argument("inputs",     nargs="?", help="Archivo de cintas/cadenas")
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--paso-a-paso", action="store_true",
                        help="Muestra cada paso y espera Enter")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Segundos entre pasos automaticos (ej: 0.5)")
    args = parser.parse_args()

    if args.definition and args.inputs:
        execute(args.definition, args.inputs, args.max_steps,
                args.paso_a_paso, args.delay)
    else:
        base = Path(__file__).resolve().parent
        print("Ejecutando ejemplos incluidos...\n")
        execute(str(base / "ejemploMTD.txt"), str(base / "cintasMTD.txt"),
                args.max_steps, args.paso_a_paso, args.delay)
        print()
        execute(str(base / "ejemploAFD.txt"), str(base / "cintasAFD.txt"),
                args.max_steps, args.paso_a_paso, args.delay)


if __name__ == "__main__":
    try:
        main()
    except (DefinitionError, FileNotFoundError) as e:
        print(f"Error: {e}")