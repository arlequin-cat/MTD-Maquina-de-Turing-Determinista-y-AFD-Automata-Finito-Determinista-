# Simulador MTD / AFD — Documentación

## ¿Qué es?

Simulador por consola de **Máquina de Turing Determinista (MTD)** y **Autómata Finito Determinista (AFD)** escrito en Python. El simulador **detecta automáticamente** el tipo de máquina según la estructura del archivo de definición, sin necesidad de declarar el tipo explícitamente.

---

## Cómo ejecutar

```bash
# Modo normal (resumen al final)
python simulador.py ejemploMTD.txt cintasMTD.txt

# Modo automático con delay entre pasos
python simulador.py ejemploMTD.txt cintasMTD.txt --delay 0.5

# Modo paso a paso (Enter para avanzar)
python simulador.py ejemploMTD.txt cintasMTD.txt --paso-a-paso

# Aumentar límite de pasos
python simulador.py ejemploMTD.txt cintasMTD.txt --max-steps 10000

# Sin argumentos — corre los ejemplos incluidos
python simulador.py

#Para linux, para ejecutar alguno de los anteriores comandos se debe realizar escribiendo de la siguiente manera:
python3 simulador.py ejemploMTD.txt cintasMTD.txt
```

---

## Detección automática de tipo

| Columnas por transición | Tipo detectado |
|-------------------------|----------------|
| 3 columnas              | AFD            |
| 5 columnas              | MTD            |

No hace falta escribir `tipo: MTD` ni `tipo: AFD` en el archivo.

---

## Formato del archivo de definición

### Cabecera (MTD)

```
start: q0          ← estado inicial (obligatorio)
accept: halt-accept
reject: halt-reject
blank: _            ← símbolo blanco (por defecto "_")
```

### Cabecera (AFD)

```
start: q0
accept: q1,q2       ← estados de aceptación (obligatorio)
```

### Transiciones MTD — 5 columnas

```
estado_actual   símbolo_lee   símbolo_escribe   dirección   siguiente_estado
```

Direcciones válidas: `r` / `d` (derecha), `l` / `i` (izquierda), `*` (no mover).

### Transiciones AFD — 3 columnas

```
estado_actual   símbolo_lee   siguiente_estado
```

---

## Lo que SÍ acepta el simulador

### Formato de transiciones

```
; Sin número de fila
0 _ m r 1
0 m m l 0
1 1 1 l 2

; Con número de fila (1, 2, 3... consecutivos — se ignoran automáticamente)
1 0 _ m r 1
2 0 m m l 0
3 1 1 1 l 2
```

El número de fila se detecta solo si la primera columna forma una secuencia estrictamente
consecutiva 1, 2, 3... Si los estados tienen nombres numéricos (0, 1, 2...) pero no son
una secuencia desde 1, se tratan como nombres de estado, no como números de fila.

### Comentarios

```
; esto es un comentario (punto y coma)
# esto también es un comentario (numeral)
0 0 _ r 1   ; comentario al final de línea
```

### Wildcard `*`

```
; En estado o símbolo leído: coincide con cualquier valor
1o * * r 1o        ; lee cualquier símbolo, escribe lo mismo, va a derecha

; En símbolo escrito o siguiente estado: significa "no cambiar"
3 1 1 * halt       ; lee 1, escribe 1, no mueve cabeza, va a halt
```

### Estados `halt`

Cualquier estado cuyo nombre empiece con `halt` detiene la máquina.

```
halt            → ACEPTA
halt-accept     → ACEPTA
halt-reject     → RECHAZA
halt-anything   → ACEPTA (solo rechaza si contiene "reject")
```

### Breakpoints con `!`

```
1 0 x r 2 !    ; la máquina pausa aquí en modo --paso-a-paso
```

### Símbolo blanco en cinta

El símbolo `_` y el espacio `" "` son equivalentes en las cintas de entrada.
Ambos se tratan como celda vacía (blanco).

```
; Estas dos cintas son idénticas para el simulador:
_1
 1
```

### Posición inicial de la cabeza con `*`

Si la cinta contiene `*`, ese carácter marca la posición inicial de la cabeza.
El `*` se elimina del contenido de la cinta antes de procesar.

```
_1          → cabeza en posición 0 (por defecto)
*_1         → cabeza en posición 0 (explícito)
1____*      → cinta = "1____", cabeza en posición 5
```

### Símbolo `:` en transiciones

```
accept * : r accept2    ; ":" es un símbolo válido de escritura
```

El parser solo interpreta `:` como separador de metadato si aparece en una
línea sin espacios antes de él (ej: `start: 0`, `blank: _`).

---

## Lo que NO acepta el simulador

| Situación | Mensaje de error |
|-----------|-----------------|
| Transiciones con columnas inconsistentes (mezcla de 3 y 5) | `Columnas inconsistentes` |
| Dirección distinta de `r`, `l`, `*` | `Movimiento invalido` |
| Transición duplicada para el mismo (estado, símbolo) | `Transicion duplicada` |
| Archivo sin ninguna transición | `No se encontraron transiciones` |
| Archivo de definición no encontrado | `Archivo no encontrado` |
| AFD sin `accept:` declarado | `Indique los estados de aceptacion` |
| 4 columnas por transición | `Se esperan 3 (AFD) o 5 (MTD)` |

### Símbolos prohibidos en el archivo de definición

Según la convención del simulador morphet (compatible con este simulador):

- `;` — reservado para comentarios
- Espacios y tabulaciones — reservados como separadores de columnas
- `*` en el archivo de definición — reservado como wildcard

Estos caracteres **sí pueden aparecer en las cintas de entrada**, pero no como
símbolos del alfabeto en las transiciones.

---

## La cinta es infinita en ambas direcciones

La cinta no es una lista de tamaño fijo. Es un `dict` de Python donde las claves
son posiciones enteras. Si la cabeza accede a una posición que no existe, devuelve
el símbolo blanco automáticamente:

```python
sym = tape.get(head, machine.blank)  # si no existe → "_"
```

Solo guarda en memoria las celdas que contienen algo distinto al blanco:

```python
tape[head] = write
if tape[head] == machine.blank:
    tape.pop(head, None)   # libera la celda si quedó en blanco
```

La cabeza puede moverse a posición `-1`, `-2`, `-100`... sin ningún límite.
No hay borde izquierdo ni derecho.

La única limitación es `--max-steps` (por defecto 1000), que no limita la cinta
sino los pasos de ejecución, para evitar bucles infinitos:

```bash
python simulador.py ejemploMTD.txt cintasMTD.txt --max-steps 10000
```

---

## Ejemplo base — MTD (identifica un 1 a la izquierda o derecha)

Máquina que recorre la cinta en ambas direcciones usando `m` como marcador
temporal, y se detiene sobre el `1` encontrado.

- **Estado 0**: si lee blanco avanza a la derecha marcando con `m`; si lee `m` retrocede
- **Estado 1**: avanza a la derecha marcando con `m` hasta encontrar un `1`
- **Estado 2**: encontró un `1`, retrocede a la izquierda limpiando los marcadores `m`
- **Estado 3**: avanza a la derecha hasta posicionarse sobre el `1` y detiene en `halt`

La cinta debe iniciar con un blanco antes de los `1`s (`_1`, `_11`, `*_1`, `*_11`).

Copia y pega en `ejemploMTD.txt`:

```
start: 0
accept: halt
blank: _

; Sin número de fila
0 _ m r 1
0 m m l 0
1 _ m r 1
1 m m r 1
1 1 1 l 2
2 m _ l 2
2 _ _ r 3
3 _ _ r 3
3 1 1 * halt

; Con número de fila (equivalente, el simulador ignora la primera columna)
; 1 0 _ m r 1
; 2 0 m m l 0
; 3 1 _ m r 1
; 4 1 m m r 1
; 5 1 1 1 l 2
; 6 2 m _ l 2
; 7 2 _ _ r 3
; 8 3 _ _ r 3
; 9 3 1 1 * halt
```

---

## Archivos del proyecto

| Archivo        | Descripción |
|----------------|-------------|
| `simulador.py` | Simulador principal |
| `ejemploMTD.txt` | Definición de la MTD de ejemplo |
| `cintasMTD.txt`  | Cintas de prueba para la MTD |
| `ejemploAFD.txt` | Definición del AFD de ejemplo |
| `cintasAFD.txt`  | Cadenas de prueba para el AFD |
