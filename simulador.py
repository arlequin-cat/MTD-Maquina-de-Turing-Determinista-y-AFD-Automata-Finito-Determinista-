# Michael Alexander Arcos Murcia - 20242678046
# Javier Santiago Ramirez Marin - 20242678010
# Github con mas instrucciones de uso:
# https://github.com/arlequin-cat/MTD-Maquina-de-Turing-Determinista-y-AFD-Automata-Finito-Determinista-
from __future__ import annotations  # Permite usar anotaciones de tipos modernas

import argparse  # Para recibir parámetros desde la consola
import time  # Para hacer pausas entre pasos
from dataclasses import dataclass, field  # Para definir estructuras simples
from pathlib import Path  # Para leer archivos
from typing import Dict, List, Set, Tuple  # Tipos de datos


class DefinitionError(Exception):
    # Error personalizado para avisar problemas en la definición de la máquina
    pass


# ─── Estructuras de datos ─────────────────────────────────────

@dataclass
class AFD:
    start: str
    # Estado inicial del autómata

    accept: Set[str]
    # Conjunto de estados de aceptación

    transitions: Dict[Tuple[str, str], str]
    # Diccionario de transiciones:
    # (estado_actual, simbolo_leido) -> estado_siguiente


@dataclass
class MTD:
    start: str
    # Estado inicial de la máquina de Turing

    blank: str
    # Símbolo blanco de la cinta (por defecto normalmente "_")

    transitions: Dict[Tuple[str, str], Tuple[str, str, str]]
    # Diccionario de transiciones:
    # (estado_actual, simbolo_leido) -> (simbolo_a_escribir, movimiento, estado_siguiente)

    breakpoints: Set[Tuple[str, str]] = field(default_factory=set)
    # Conjunto de puntos de interrupción opcionales para detener la ejecución
    # en ciertas transiciones y revisar paso a paso


# ─── Parser ───────────────────────────────────────────────────

def _is_row_number_column(rows: List[List[str]]) -> bool:
    """
    Verifica si la primera columna es solo numeración de filas:
    1, 2, 3, ... o 01, 02, 03, ...

    Esto se hace para no confundir esos números con estados reales
    llamados 0, 1, 2, etc.
    """
    try:
        nums = [int(r[0]) for r in rows]
    except ValueError:
        return False
    return nums == list(range(1, len(nums) + 1))


def parse_file(path: str):
    """
    Lee el archivo de definición de la máquina.

    Aquí se:
    1. eliminan comentarios,
    2. separan metadatos (start:, accept:, blank:),
    3. guardan las transiciones,
    4. detecta automáticamente si el archivo describe un AFD o una MTD.

    Regla usada:
    - 3 columnas = AFD
    - 5 columnas = MTD
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    meta: Dict[str, str] = {}
    rows: List[dict] = []

    for raw in lines:
        # Se eliminan comentarios con ';' o '#'
        line = raw.split(";")[0].split("#")[0].strip()

        if not line:
            continue

        # Si termina en '!' se guarda como breakpoint
        breakpoint_flag = line.endswith("!")
        if breakpoint_flag:
            line = line[:-1].strip()

        # Si tiene ':' puede ser un metadato como start: q0
        if ":" in line:
            k, _, v = line.partition(":")
            if " " not in k.strip():
                # Solo se considera metadato si la clave es una sola palabra
                meta[k.strip().lower()] = v.strip()
                continue

            # Si no era metadato, se trata como transición normal
            parts = line.split()
            if parts:
                rows.append({"parts": parts, "bp": breakpoint_flag})
        else:
            parts = line.split()
            if parts:
                rows.append({"parts": parts, "bp": breakpoint_flag})

    if not rows:
        raise DefinitionError("No se encontraron transiciones.")

    # Si la primera columna era solo numeración, se elimina
    if _is_row_number_column([r["parts"] for r in rows]):
        for r in rows:
            r["parts"] = r["parts"][1:]

    # Todas las filas deben tener el mismo número de columnas
    widths = {len(r["parts"]) for r in rows}
    if len(widths) != 1:
        raise DefinitionError(
            f"Columnas inconsistentes en las transiciones: {widths}. "
            "Se esperan 3 (AFD) o 5 (MTD)."
        )

    width = widths.pop()

    # Detección automática del tipo de máquina
    if width == 3:
        return _build_afd(meta, rows)
    if width == 5:
        return _build_mtd(meta, rows)

    raise DefinitionError(
        f"Las transiciones tienen {width} columna(s). "
        "Se esperan 3 (AFD) o 5 (MTD)."
    )


def _build_afd(meta, rows):
    """
    Construye un AFD a partir de las filas leídas.

    En un AFD cada transición debe ser única:
    (estado, símbolo) no puede repetirse,
    porque por definición el AFD es determinista.
    """
    transitions: Dict[Tuple[str, str], str] = {}

    for r in rows:
        state, symbol, nxt = r["parts"]
        key = (state, symbol)

        # Si una transición ya existe, deja de ser determinista
        if key in transitions:
            raise DefinitionError(f"Transicion duplicada AFD: ({state}, {symbol})")

        transitions[key] = nxt

    # Si no se especifica start:, toma el primer estado encontrado
    start = meta.get("start") or meta.get("inicial") or rows[0]["parts"][0]

    # Estados de aceptación, separados por coma
    accept_raw = (meta.get("accept") or meta.get("aceptacion")
                  or meta.get("final") or "")
    accept = {s.strip() for s in accept_raw.split(",") if s.strip()}

    if not accept:
        raise DefinitionError("Indique estados de aceptacion: 'accept: q1,q2'")

    return "AFD", AFD(start=start, accept=accept, transitions=transitions)


def _build_mtd(meta, rows):
    """
    Construye una Máquina de Turing Determinista.

    Cada transición tiene la forma:
    estado_actual, simbolo_leido -> simbolo_escrito, movimiento, estado_siguiente

    El movimiento debe ser:
    - l : izquierda
    - r : derecha
    - * : no mover la cabeza
    """
    transitions: Dict[Tuple[str, str], Tuple[str, str, str]] = {}
    breakpoints: Set[Tuple[str, str]] = set()

    for r in rows:
        state, read, write, move, nxt = r["parts"]
        key = (state, read)

        # También debe ser determinista: no puede repetirse (estado, símbolo)
        if key in transitions:
            raise DefinitionError(f"Transicion duplicada MTD: ({state}, {read})")

        move = move.lower()
        if move not in {"l", "r", "*"}:
            raise DefinitionError(f"Movimiento invalido '{move}'. Use l, r o *.")

        transitions[key] = (write, move, nxt)

        # Si la fila tenía '!' se marca como breakpoint
        if r["bp"]:
            breakpoints.add(key)

    start = meta.get("start") or meta.get("inicial") or rows[0]["parts"][0]
    blank = meta.get("blank") or meta.get("blanco") or "_"

    return "MTD", MTD(
        start=start,
        blank=blank,
        transitions=transitions,
        breakpoints=breakpoints
    )


# ─── Lectura de entradas ──────────────────────────────────────

def read_inputs(path: str) -> List[str]:
    """
    Lee el archivo de entradas.

    - En AFD: cada línea es una cadena
    - En MTD: cada línea representa una cinta inicial

    No elimina espacios internos; solo quita el salto de línea final.
    También ignora líneas que sean comentarios.
    """
    inputs = []

    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith(("#", ";")):
            continue
        inputs.append(raw.rstrip("\n"))

    return inputs


# ─── Parseo de cinta ──────────────────────────────────────────

def parse_tape(word: str) -> Tuple[dict, int]:
    """
    Convierte una cadena en la cinta de la máquina de Turing.

    La cinta se guarda como un diccionario:
    posición -> símbolo

    Esto es importante porque NO se usa una lista fija.
    Así la cinta se comporta como una cinta potencialmente infinita
    hacia izquierda y derecha:
    si la cabeza se mueve a una posición nueva, esa celda simplemente
    se asume blanca cuando se consulte.

    Entonces:
    - físicamente en memoria no es infinita,
    - pero lógicamente sí se comporta como una cinta extendible.

    Si existe '*', ese símbolo marca la posición inicial de la cabeza.
    Luego el '*' se elimina del contenido real de la cinta.
    """
    if "*" in word:
        head = word.index("*")
        word = word[:head] + word[head + 1:]
    else:
        head = 0

    # Los espacios se reemplazan por '_' para tratarlos como blancos visibles
    tape = {i: ch for i, ch in enumerate(word.replace(" ", "_"))}
    return tape, head


# ─── Visualización de cinta ───────────────────────────────────

WINDOW = 10


# Cantidad de celdas que se muestran a cada lado de la cabeza
# Esto es solo para imprimir la cinta; no limita realmente su tamaño


def _tape_display(tape: dict, blank: str, head: int) -> str:
    """
    Muestra una ventana de la cinta alrededor de la cabeza.
    La celda actual se encierra en [ ].
    """
    cells = []

    for i in range(head - WINDOW, head + WINDOW + 1):
        sym = tape.get(i, blank)  # Si la posición no existe, se asume blanca
        cells.append(f"[{sym}]" if i == head else f" {sym} ")

    return "".join(cells)


def _tape_arrow(head: int) -> str:
    """
    Dibuja una flecha debajo de la cabeza.
    La cabeza siempre se imprime en el centro de la ventana visual.
    """
    pos = WINDOW
    spaces = pos * 3 + 1
    return " " * spaces + "^"


def _tape_raw(tape: dict, blank: str) -> str:
    """
    Devuelve el contenido útil final de la cinta.

    Toma desde la posición mínima usada hasta la máxima usada,
    ignorando blancos externos innecesarios.
    """
    used = [i for i, v in tape.items() if v != blank]

    if not used:
        return blank

    lo, hi = min(used), max(used)
    return "".join(tape.get(i, blank) for i in range(lo, hi + 1))


# ─── Búsqueda de transiciones con comodines ───────────────────

def _lookup(transitions, state, sym):
    """
    Busca una transición en este orden de prioridad:

    1. (estado exacto, símbolo exacto)
    2. (estado exacto, '*')
    3. ('*', símbolo exacto)
    4. ('*', '*')

    Esto permite usar comodines en la definición de la máquina.

    Además:
    - si write == '*', significa "escriba el mismo símbolo leído"
    - si nxt == '*', significa "quédese en el mismo estado"
    """
    for s, c in [(state, sym), (state, "*"), ("*", sym), ("*", "*")]:
        if (s, c) in transitions:
            write, move, nxt = transitions[(s, c)]

            write = sym if write == "*" else write
            nxt = state if nxt == "*" else nxt

            return write, move, nxt, (s, c)

    return None


# ─── Ejecución del AFD ────────────────────────────────────────

def run_afd(machine: AFD, word: str, step_mode: bool, delay: float) -> dict:
    """
    Ejecuta una cadena sobre un AFD.

    El AFD:
    - lee la cadena de izquierda a derecha,
    - no modifica la entrada,
    - no se devuelve,
    - termina cuando se acaba la cadena.

    Por eso, la ejecución del AFD siempre es finita respecto al tamaño
    de la entrada: hace como máximo un paso por símbolo.
    """
    state = machine.start
    path = [state]
    visual = step_mode or delay > 0
    SEP = "-" * 55

    if visual:
        print(f"\n  Cadena : '{word}'")
        print(f"  Inicio : {state}")
        print(SEP)

    for i, ch in enumerate(word):
        key = (state, ch)

        # Si no hay transición para el símbolo actual, la cadena se rechaza
        if key not in machine.transitions:
            if visual:
                print(f"  Paso {i + 1:>3}: ({state}, '{ch}') -> sin transicion -> RECHAZA")
            return {
                "entrada": word,
                "aceptada": False,
                "motivo": f"Sin transicion para ({state}, {ch})",
                "estado_final": state,
                "recorrido": " -> ".join(path)
            }

        nxt = machine.transitions[key]

        if visual:
            print(f"  Paso {i + 1:>3}: estado={state:<10} lee='{ch}'  ->  {nxt}")
            _wait(step_mode, delay)

        state = nxt
        path.append(state)

    # Solo acepta si el estado final pertenece al conjunto de aceptación
    ok = state in machine.accept

    if visual:
        print(f"\n  Fin: estado={state}  ->  {'ACEPTADA' if ok else 'RECHAZADA'}")

    return {
        "entrada": word,
        "aceptada": ok,
        "motivo": "Cadena aceptada" if ok else "Estado final no aceptador",
        "estado_final": state,
        "recorrido": " -> ".join(path)
    }


# ─── Ejecución de la MTD ──────────────────────────────────────

def run_mtd(machine: MTD, word: str, max_steps: int,
            step_mode: bool, delay: float) -> dict:
    """
    Ejecuta una Máquina de Turing Determinista.

    A diferencia del AFD:
    - sí puede escribir en la cinta,
    - puede moverse a izquierda o derecha,
    - la cinta se trata como extendible,
    - puede entrar en ciclos.

    Por eso aquí sí se necesita:
    - detección de ciclos,
    - límite máximo de pasos.
    """
    tape, head = parse_tape(word)
    state = machine.start
    blank = machine.blank
    seen: set = set()
    visual = step_mode or delay > 0
    SEP = "-" * (WINDOW * 2 * 3 + 10)

    def show_step(step: int, info: str = ""):
        """
        Muestra el estado actual de la simulación:
        - número de paso
        - estado
        - posición de la cabeza
        - cinta alrededor de la cabeza
        """
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
        # Lee el símbolo actual; si esa celda no existe, se asume blanca
        sym = tape.get(head, blank)

        # Snapshot = fotografía completa de la configuración actual
        # Si se repite exactamente, la máquina cayó en un ciclo
        snapshot = (
            state,
            head,
            tuple(sorted((k, v) for k, v in tape.items() if v != blank))
        )

        if snapshot in seen:
            return {
                "entrada": word,
                "aceptada": False,
                "motivo": "Ciclo detectado",
                "estado_final": state,
                "pasos": step,
                "cinta_final": _tape_raw(tape, blank)
            }

        seen.add(snapshot)

        # Convención: si el estado empieza por "halt", la máquina se detiene
        if state.startswith("halt"):
            ok = "reject" not in state

            if visual:
                print(f"\n  Detenida en '{state}'  ->  {'ACEPTADA' if ok else 'RECHAZADA'}")

            return {
                "entrada": word,
                "aceptada": ok,
                "motivo": f"Estado halt: {state}",
                "estado_final": state,
                "pasos": step - 1,
                "cinta_final": _tape_raw(tape, blank)
            }

        # Busca la transición aplicable
        tr = _lookup(machine.transitions, state, sym)

        if tr is None:
            # Si no existe transición, la máquina se detiene rechazando
            if visual:
                print(f"\n  Sin transicion para ({state}, '{sym}')  ->  RECHAZADA")
            return {
                "entrada": word,
                "aceptada": False,
                "motivo": f"Sin transicion para ({state}, {sym})",
                "estado_final": state,
                "pasos": step,
                "cinta_final": _tape_raw(tape, blank)
            }

        write, move, nxt, key = tr
        info = f"({state}, '{sym}') -> escribe='{write}'  dir={move}  -> {nxt}"

        # Escribe en la celda actual
        tape[head] = write

        # Si quedó en blanco, se elimina del diccionario para ahorrar espacio.
        # Esto refuerza la idea de que solo guardamos las celdas útiles.
        if tape[head] == blank:
            tape.pop(head, None)

        # Movimiento de la cabeza
        if move == "r":
            head += 1
        elif move == "l":
            head -= 1
        # Si move == "*" no se mueve

        # Cambio de estado
        state = nxt

        if visual:
            show_step(step, info)

            # Si esa transición fue marcada como breakpoint, se detiene
            is_bp = key in machine.breakpoints
            if is_bp:
                print("  *** BREAKPOINT ***")

            if step_mode or is_bp:
                input("  [Enter para continuar]")
            else:
                time.sleep(delay)

    # Si llega aquí, se alcanzó el máximo de pasos permitidos
    return {
        "entrada": word,
        "aceptada": False,
        "motivo": f"Limite de {max_steps} pasos alcanzado",
        "estado_final": state,
        "pasos": max_steps,
        "cinta_final": _tape_raw(tape, blank)
    }


def _wait(step_mode: bool, delay: float):
    """
    Controla la pausa entre pasos:
    - paso a paso: espera Enter
    - automático: espera el tiempo indicado
    """
    if step_mode:
        input("  [Enter para continuar]")
    elif delay > 0:
        time.sleep(delay)


# ─── Ejecución general ────────────────────────────────────────

def execute(definition: str, inputs_file: str, max_steps: int,
            step_mode: bool, delay: float):
    """
    Función principal de ejecución.

    Aquí se:
    1. carga la definición,
    2. detecta si es AFD o MTD,
    3. leen las entradas,
    4. se ejecuta cada una,
    5. se imprime el resumen final.
    """
    mtype, machine = parse_file(definition)
    entries = read_inputs(inputs_file)
    visual = step_mode or delay > 0
    SEP = "=" * 65

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

        # Si no está en modo visual detallado, imprime un resumen corto por entrada
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
          f"Aceptadas={ok}  Rechazadas={len(results) - ok}")
    print(SEP)


# ─── Main ─────────────────────────────────────────────────────

def main():
    """
    Punto de entrada del programa.

    Permite ejecutar desde consola, por ejemplo:
    python simulador.py maquina.txt entradas.txt

    También permite:
    --max-steps
    --paso-a-paso
    --delay
    """
    parser = argparse.ArgumentParser(
        description="Simulador MTD/AFD — detecta el tipo automaticamente."
    )

    parser.add_argument("definition", nargs="?", help="Archivo de la maquina")
    parser.add_argument("inputs", nargs="?", help="Archivo de cintas/cadenas")
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument(
        "--paso-a-paso",
        action="store_true",
        help="Muestra cada paso y espera Enter"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Segundos entre pasos automaticos (ej: 0.5)"
    )

    args = parser.parse_args()

    # Si se pasan archivos por consola, usa esos
    if args.definition and args.inputs:
        execute(
            args.definition,
            args.inputs,
            args.max_steps,
            args.paso_a_paso,
            args.delay
        )
    else:
        # Si no se pasan archivos, ejecuta ejemplos incluidos en la carpeta
        base = Path(__file__).resolve().parent
        print("Ejecutando ejemplos incluidos...\n")

        execute(
            str(base / "ejemploMTD.txt"),
            str(base / "cintasMTD.txt"),
            args.max_steps,
            args.paso_a_paso,
            args.delay
        )

        print()

        execute(
            str(base / "ejemploAFD.txt"),
            str(base / "cintasAFD.txt"),
            args.max_steps,
            args.paso_a_paso,
            args.delay
        )


if __name__ == "__main__":
    try:
        main()
    except (DefinitionError, FileNotFoundError) as e:
        # Captura errores de definición o archivos faltantes
        print(f"Error: {e}")