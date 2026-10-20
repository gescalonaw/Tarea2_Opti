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

## Estructura relevante del repo

```
.
├── modelo.py                          # lee la instancia y arma el modelo (variables, restricciones)
├── resolver.py                        # corre el modelo end-to-end y guarda resultados
├── sensibilidad.py                    # análisis de sensibilidad de Q con Model.fixed()
├── generador/
│   └── data/
│       └── instancias/
│           ├── instancia_A.json
│           └── instancia_B.json
└── resultados/                        # se crea sola al correr resolver.py
    ├── instancia_A.txt
    └── instancia_B.txt
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


