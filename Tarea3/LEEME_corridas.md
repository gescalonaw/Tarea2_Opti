# TC3 — Instrucciones para quien hace las corridas
Todo se corre desde esta carpeta (`Tarea 3`).
Los comandos están escritos para **Git Bash**. En PowerShell, cambia `/` por `\` en las rutas.

## 1. Entorno de Python

```bash
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```
**Gurobi:** `requirements.txt` instala Gurobi 13, la misma versión del notebook de apoyo del ayudante (Gurobi 13.0.1 y CPLEX 22.2.0). La licencia tiene que ser de esa versión: abre `C:\Users\<tu usuario>\gurobi.lic` y busca la línea `VERSION=`. Si dice otra (por ejemplo 12), instala esa:
```bash
./.venv/Scripts/python.exe -m pip install "gurobipy==12.*"
```

## 2. CPLEX académico

1. Conéctalo con el entorno:
   ```bash
   ls "/c/Program Files/IBM/ILOG/"
   ./.venv/Scripts/docplex.exe config --upgrade "C:/Program Files/IBM/ILOG/CPLEX_Studio222"
   ```
   Si el `ls` muestra otro nombre de carpeta, usa ese.

## 3. Verificar que los dos solvers tengan licencia completa

```bash
./.venv/Scripts/python.exe codigo/verificar_instalacion.py
```

Tiene que decir **"Todo listo para la corrida oficial"**. Si dice FALLA, el mensaje explica qué falta. Anota el procesador que aparece en la primera línea: va en el pitch.

## 4. Prueba rápida (~3 min)

```bash
./.venv/Scripts/python.exe codigo/correr_todo.py instancias/instancia_A_corregida.json instancias/instancia_B_corregida.json --time-limit 30 --salida prueba
```

Revisa tres cosas:
- En la instancia B, **z_LP = 111.9455** en Gurobi y en CPLEX.
- Cada solver dice **"validacion: ... OK"**.
- Las líneas "Relajacion: diferencia de objetivo Gurobi-CPLEX" muestran diferencias muy chicas (del orden de 1e-9 o menos).

## 5. Corrida oficial (~40 min)

```bash
./.venv/Scripts/python.exe codigo/correr_todo.py instancias/instancia_A_corregida.json instancias/instancia_B_corregida.json
```

Hace lo mismo que el notebook de apoyo de la TC3: para cada instancia resuelve la relajación (Gurobi con `m.relax()`, CPLEX con `LinearRelaxer`) y luego el entero, en ambos solvers, con la configuración por defecto. Lo único que se fija es el límite de 600 s, igual para los dos. Cada LP se resuelve 5 veces y se promedia su tiempo.

Queda todo en `resultados/`:
- `comparacion_gurobi_cplex.txt` y `.csv` con el mismo formato del notebook (instancia, tipo, solver, objetivo, tiempo_s, nodos, gap). El `.csv` además trae la cota, la brecha de integralidad y si la solución pasó la validación.
- `logs/`: los 8 archivos `.log` que pide la entrega.
- `*_rutas.json`: las rutas de cada solución.



## Scripts por separado (no lo pide pero porsiaca)

| Script | Qué hace |
| --- | --- |
| `codigo/relajacion.py` | Solo la relajación continua en ambos solvers → `resultados/relajacion.txt` |
| `codigo/entero.py` | Solo el modelo entero en ambos solvers → `resultados/entero.txt` |
| `codigo/correr_todo.py` | Las dos cosas y la tabla comparativa (la corrida oficial) |
| `codigo/graficar.py` | Gráficos de instancias y de rutas |

Todos aceptan `--solo gurobi` o `--solo cplex` y `--salida <carpeta>`. Los de relajación aceptan `--repeticiones` (por defecto 5). Los de modelo entero aceptan `--time-limit` y `--verbose`.
