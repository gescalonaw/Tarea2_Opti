# Tarea2_Opti

Modelo de ruteo de vehículos con consistencia (conVRP-SLA, versión reducida) resuelto con Gurobi. Este README explica cómo correr `resolver.py` para obtener los resultados sobre una instancia.

## Requisitos

- Python 3.9+
- [Gurobi](https://www.gurobi.com/) instalado con una licencia válida (licencia académica gratuita — pídela con tu correo @udec.cl en https://www.gurobi.com/academia/academic-program-and-licenses/)
- Paquete `gurobipy`:

```bash
pip install gurobipy
```

Si Gurobi está instalado pero no reconoce la licencia, corre `grbgetkey <tu-clave>` siguiendo las instrucciones que te llegan al activar la licencia académica.

### Entorno virtual del repo

Si tu `python` del PATH no tiene `gurobipy` (por ejemplo, `ModuleNotFoundError: No module named 'gurobipy'`, o el error `externally-managed-environment` de MSYS2), usa el entorno virtual `.venv` del repo, que apunta al Python oficial y ya trae `gurobipy`:

```powershell
.\.venv\Scripts\python.exe resolver.py generador/data/instancias/instancia_A.json
.\.venv\Scripts\python.exe sensibilidad.py generador/data/instancias/instancia_A.json
.\.venv\Scripts\python.exe tuning.py generador/data/instancias/instancia_A.json
```

Para recrearlo desde cero (si clonas el repo en otro equipo):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install gurobipy
```

La carpeta `.venv/` está en `.gitignore`, así que no se sube al repo. Alternativa sin venv: usar `py -3.13` directamente, que apunta al Python oficial donde ya está instalado `gurobipy`.

## Estructura relevante del repo

```
.
├── modelo.py                          # lee la instancia y arma el modelo (variables, restricciones)
├── resolver.py                        # corre el modelo end-to-end y guarda resultados
├── configuraciones_solver.py          # compara baseline vs 5 variaciones de parámetros (sección 4.2)
├── relajacion.py                      # relajación continua y brecha de integralidad (sección 4.1)
├── sensibilidad.py                    # análisis de sensibilidad de Q con Model.fixed()
├── tuning.py                          # ajuste automático de parámetros con Model.tune()
├── generador/
│   └── data/
│       └── instancias/
│           ├── instancia_A.json
│           └── instancia_B.json
└── resultados/                        # se crea sola al correr los scripts
    ├── instancia_A.txt
    ├── instancia_B.txt
    └── configuraciones_solver.txt
```

## Cómo correrlo

Desde la **raíz del repo** (donde están `modelo.py` y `resolver.py`):

```bash
python resolver.py generador/data/instancias/instancia_A.json
python resolver.py generador/data/instancias/instancia_B.json
```

Esto imprime en pantalla el progreso de Gurobi (log del solver), la distancia total, el gap final, el tiempo de ejecución, y el detalle de cada ruta por día. Además guarda una copia en texto plano en `resultados/<nombre_instancia>.txt`.

### Parámetros por defecto

- `Threads = 1`
- `TimeLimit = 600` segundos (el límite que pide el enunciado)

### Correr con otro límite de tiempo (pruebas rápidas)

Puedes pasar un segundo argumento para cambiar el `TimeLimit` sin tocar el código, por ejemplo 60 segundos:

```bash
python resolver.py generador/data/instancias/instancia_A.json 60
```

### Probar tus propias instancias

Si generas una instancia nueva (por ejemplo con más clientes para hacerla más difícil), solo pásale la ruta del `.json` correspondiente:

```bash
python resolver.py ruta/a/tu_instancia.json
```

No hace falta modificar `resolver.py` ni `modelo.py` para esto — el nombre de la instancia y sus resultados se toman directamente del JSON.

## Configuraciones del solver

`configuraciones_solver.py` resuelve el modelo entero 6 veces sobre **instancia_A** (la instancia de referencia que pide el enunciado para esta comparación): una vez con la configuración por defecto (**Base**) y luego cambiando **un solo parámetro a la vez**, dejando todo lo demás en su valor por defecto:

- `Cuts = 0`
- `Presolve = 0`
- `MIPFocus = 1`
- `MIPFocus = 3`
- `Heuristics = 0`

En las 6 corridas se mantiene fijo `Threads = 1` y `TimeLimit = 600`. Cada corrida arma un modelo **nuevo** (no reutiliza el mismo objeto `Model` entre configuraciones), para que los parámetros y el estado de búsqueda de una corrida no contaminen la siguiente.

```bash
python configuraciones_solver.py
```

No recibe argumentos — la instancia y los parámetros fijos ya están definidos en el script. Imprime tiempo, gap final y valor objetivo de cada configuración a medida que van terminando, y guarda el resumen de las 6 en `resultados/configuraciones_solver.txt`.

Como son 6 corridas y cada una puede tardar hasta 600 s si no cierra el gap antes, el script completo puede demorar varios minutos.

## Relajación continua

`relajacion.py` calcula la relajación continua del modelo (quitando la integralidad de las variables binarias con `Model.relax()`) y la brecha de integralidad respecto al óptimo entero, sobre **instancia_A**:

```bash
python relajacion.py
```

No recibe argumentos — la ruta de la instancia (`generador/data/instancias/instancia_A.json`) está fija dentro del script. Imprime en consola:

```
z_LP = <valor> | z* = <valor> | brecha de integralidad = <valor> %
```

- **z\*** es el óptimo entero (resuelve el modelo normal, igual que `resolver.py`).
- **z_LP** es el valor óptimo de la relajación continua (el mismo modelo sin exigir integralidad).
- **brecha** es `100 * (z* − z_LP) / z*`: qué tan lejos está el LP del óptimo entero real.

Este script no guarda archivo de salida, solo imprime en consola. Si quieren correrlo también sobre instancia_B, hay que editar manualmente la ruta del archivo dentro de `relajacion.py` (no toma la instancia por línea de comandos como sí lo hacen `resolver.py`, `sensibilidad.py` y `tuning.py`).

## Análisis de sensibilidad de Q

`sensibilidad.py` corre el mismo modelo que `resolver.py` (misma CLI: instancia y límite de tiempo opcional, 600 s por defecto) y además:

1. Resuelve el MIP y reporta el estado decodificado (p. ej. `OPTIMAL`, `TIME_LIMIT`), la distancia total, la cota inferior (`ObjBound`), el gap y el tiempo. Si `Status != OPTIMAL` pero hay solución, advierte explícitamente que el análisis se hace sobre la **mejor incumbente** y no sobre un óptimo certificado. Si no hay ninguna solución dentro del límite, lo informa y no continúa.
2. Fija las variables enteras (`X`, `Z`) con `Model.fixed()` y resuelve el PL resultante para reportar, por cada restricción `capacidad[r,t]`, la carga, el RHS, `Pi` (precio sombra), `Slack`, `SARHSLow` y `SARHSUp`. Si el PL fijo no termina en óptimo, lo informa y no lee los atributos de sensibilidad.
3. Interpreta la tabla a partir de los valores obtenidos (el texto depende de la instancia):
   - **Rango de validez de Q**: `[máx SARHSLow, mín SARHSUp]`, en valores absolutos de RHS, donde la base óptima del PL fijo (y por tanto `Pi`) sigue siendo válida. `máx SARHSLow` es el Q mínimo con el que la asignación actual (`Z`) sigue siendo factible.
   - **Precio sombra**: si `Pi = 0` en todas las restricciones, lo explica (con `X` y `Z` fijas la fila de capacidad no tiene variables libres y `Z` no aparece en el objetivo, así que el PL fijo no puede reasignar clientes; esto no implica que Q sea irrelevante en el MIP). Si hay `Pi ≠ 0`, las lista con su valor.
   - **Restricciones activas** (`Slack = 0`), restricciones con `SARHSUp` finito, carga máxima y holgura mínima respecto a Q.

Los resultados se guardan en `resultados/sensibilidad_<nombre_instancia>.txt`.

```bash
python sensibilidad.py generador/data/instancias/instancia_A.json
python sensibilidad.py generador/data/instancias/instancia_B.json 60
```

Guarda el reporte en `resultados/sensibilidad_<nombre_instancia>.txt`.

## Ajuste automático de parámetros (Model.tune())

`tuning.py` corre el mismo modelo que `resolver.py` (misma CLI de instancia) y ajusta automáticamente los parámetros del solver con `Model.tune()`:

1. Resuelve el MIP con las **opciones manuales** (editables en el archivo o por `--opciones`) para tener una línea base reproducible.
2. Corre `Model.tune()`, que prueba distintos conjuntos de parámetros y se queda con los que mejoran el desempeño. El criterio primario del tuner es minimizar el tiempo hasta optimalidad certificada; si el modelo no cierra dentro del límite, usa un criterio secundario automático (gap u objetivo).
3. Reporta el caso base y **todos** los conjuntos devueltos, marcando el mejor y las diferencias contra el caso base. Recuerda que el resultado `0` es siempre el caso base y el `1` el mejor hallado (por eso se retienen al menos 2).
4. Verifica el mejor conjunto: lo re-resuelve sobre la instancia, lo compara contra las opciones manuales, repite la corrida para chequear reproducibilidad y deja el conjunto listo para pegar en `resolver.py`.

```bash
python tuning.py generador/data/instancias/instancia_A.json
python tuning.py generador/data/instancias/instancia_B.json --tiempo-tune 300
python tuning.py generador/data/instancias/instancia_A.json --limite-solve 120 --trials 2 --seed 7
python tuning.py generador/data/instancias/instancia_B.json --limite-solve 120 --trials 2 --seed 7
python tuning.py --opciones "MIPFocus=1;Heuristics=0.3"   # caso base manual
```

Opciones principales: `--limite-solve` (TimeLimit por solve), `--tiempo-tune` (TuneTimeLimit), `--trials` (TuneTrials), `--results` (TuneResults), `--seed`, `--criterio` (TuneCriterion), `--threads` / `--hilos-tune`, `--no-verificar` y `--salida-tuner` (guarda el detalle del tuner). El reporte se guarda en `resultados/tuning_<nombre_instancia>.txt`.
