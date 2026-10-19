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


