"""
Analisis de sensibilidad de la restriccion de capacidad Q (14) sobre la solucion optima (o mejor incumbente) del MIP.

Pasos:
    1. Resuelve el MIP (Threads=1, TimeLimit configurable, por defecto 600 s) y toma la solución óptima o, si no se probó optimalidad, la mejor incumbente.
    2. Fija las variables enteras con Model.fixed() y resuelve el PL resultante.

Uso (desde la raiz del repo):
    python sensibilidad.py generador/data/instancias/instancia_A.json
    python sensibilidad.py generador/data/instancias/instancia_B.json 60
"""
import os
import sys
 
from gurobipy import GRB
from modelo import leer_instancia, armar_modelo
 
archivo = sys.argv[1] if len(sys.argv) > 1 else "generador/data/instancias/instancia_A.json"
LIMITE = float(sys.argv[2]) if len(sys.argv) > 2 else 600  # segundos (600 x el enunciado)
 
TOL = 1e-6
INF = 1e99
 
lineas = []
 
 
def emitir(linea=""):
    """Imprime y acumula la línea para guardarla en resultados/."""
    print(linea)
    lineas.append(linea)
 
 
def formato(valor, dec=1):
    """Formatea un atributo de Gurobi que puede ser infinito."""
    if abs(valor) >= INF:
        return '+inf' if valor > 0 else '-inf'
    return f'{valor:.{dec}f}'
 
 
NOMBRES_ESTADO = {
    GRB.OPTIMAL: "OPTIMAL",
    GRB.INFEASIBLE: "INFEASIBLE",
    GRB.INF_OR_UNBD: "INF_OR_UNBD",
    GRB.UNBOUNDED: "UNBOUNDED",
    GRB.CUTOFF: "CUTOFF",
    GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
    GRB.NODE_LIMIT: "NODE_LIMIT",
    GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
    GRB.TIME_LIMIT: "TIME_LIMIT",
    GRB.INTERRUPTED: "INTERRUPTED",
    GRB.NUMERIC: "NUMERIC",
    GRB.SUBOPTIMAL: "SUBOPTIMAL",
    GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT",
    GRB.WORK_LIMIT: "WORK_LIMIT",
    GRB.MEM_LIMIT: "MEM_LIMIT",
}
 
 
def estado(modelo):
    return NOMBRES_ESTADO.get(modelo.Status, f"estado {modelo.Status}")
 
 
d = leer_instancia(archivo)
n, T, R, Q, q = d['n'], d['T'], d['R'], d['Q'], d['q']
emitir(f"Instancia: {d['nombre']} | clientes = {n} | días = {T} | rutas = {R} | Q = {Q}")
 
# ---------- 1. Solución óptima (o mejor incumbente) ----------
m, X, Z, W, cap = armar_modelo(d)
m.Params.OutputFlag = 1   # ver el log de Gurobi mientras resuelve
m.Params.Threads = 1
m.Params.TimeLimit = LIMITE
m.optimize()
 
emitir("")
if m.SolCount == 0:
    emitir(f"Sin solución dentro del límite de tiempo. Estado: {estado(m)}. No se puede hacer el análisis.")
else:
    base_optima = (m.Status == GRB.OPTIMAL)
    emitir(f"Estado = {estado(m)} | distancia total = {m.ObjVal:.1f} | cota inferior = {m.ObjBound:.1f} | "
           f"gap = {100*m.MIPGap:.2f} % | tiempo = {m.Runtime:.1f} s (límite {LIMITE:.0f} s)")
    if not base_optima:
        emitir("ADVERTENCIA: no se probó optimalidad; el análisis se hace sobre la MEJOR INCUMBENTE.")
        emitir("Las holguras y rutas llenas podrían diferir de las del óptimo.")
    emitir("")
 
    z_base = {k: round(v.X) for k, v in Z.items()}
 
    # ---------- 2. Sensibilidad de Q con variables enteras fijadas ----------
    emitir("=" * 70)
    emitir("Análisis de sensibilidad: restricción de capacidad Q con Model.fixed()")
    emitir("Se fijan las variables enteras (X, Z) en la solución encontrada y se")
    emitir("resuelve el PL resultante para leer la dualidad de capacidad[r,t].")
    emitir("=" * 70)
    emitir("")
 
    fijo = m.fixed()
    fijo.Params.OutputFlag = 0
    fijo.optimize()
 
    if fijo.Status != GRB.OPTIMAL:
        emitir(f"El PL con enteras fijas no terminó en óptimo (estado: {estado(fijo)}); "
               f"no se pueden leer Pi ni SARHS.")
    else:
        emitir(f"{'restricción':18s} {'carga':>7s} {'RHS':>7s} {'Pi':>7s} {'Slack':>7s} "
               f"{'SARHSLow':>9s} {'SARHSUp':>9s}")
        filas = []  # (r, t, carga, Pi, Slack, SARHSLow, SARHSUp)
        for r in range(R):
            for t in range(T):
                c = fijo.getConstrByName(f'capacidad[{r},{t}]')
                carga = sum(q[i][t] * z_base[(i, r)] for i in range(1, n + 1))
                filas.append((r, t, carga, c.Pi, c.Slack, c.SARHSLow, c.SARHSUp))
                emitir(f"{c.ConstrName:18s} {carga:7.0f} {formato(c.RHS):>7s} {formato(c.Pi, 3):>7s} "
                       f"{formato(c.Slack):>7s} {formato(c.SARHSLow):>9s} {formato(c.SARHSUp):>9s}")
        emitir("")
 
        # --- Resumen derivado de los valores (válido para cualquier instancia) ---
        activas = [(r, t) for r, t, _, _, s, _, _ in filas if abs(s) < TOL]
        con_precio = [(r, t, pi) for r, t, _, pi, _, _, _ in filas if abs(pi) > 1e-9]
        r_max, t_max, carga_max = max(((r, t, c) for r, t, c, *_ in filas), key=lambda x: x[2])
        rangos_finitos_up = [(r, t, up) for r, t, _, _, _, _, up in filas if up < INF]
 
        emitir("Interpretación:")
        emitir("  - Pi (precio sombra): cambio de la distancia total por cada unidad adicional de Q,")
        emitir("    mientras Q permanezca en [SARHSLow, SARHSUp]. En minimización con restricción <=,")
        emitir("    Pi <= 0: un valor negativo indica que relajar la capacidad reduciría la distancia.")
        emitir("  - Slack = Q - carga. Slack = 0 significa ruta llena (restricción activa).")
        emitir("  - [SARHSLow, SARHSUp]: rango del RHS en que la base óptima del PL fijo, y por tanto")
        emitir("    el Pi reportado, sigue siendo válida.")
        emitir("")
        emitir("Resultados sobre esta solución:")

        sarhslow_max = max(f[5] for f in filas)
        sarhsup_min = min(f[6] for f in filas)
        emitir(f"  - Rango de validez de Q (valores absolutos de RHS): [máx SARHSLow, mín SARHSUp] = "
               f"[{formato(sarhslow_max)}, {formato(sarhsup_min)}].")
        emitir(f"    Q mínimo de la asignación actual = máx SARHSLow = {sarhslow_max:.0f}: por debajo")
        emitir(f"    de ese valor la asignación fijada (Z) dejaría de ser factible.")
 
        if not con_precio:
            emitir(f"  - Pi = 0 en las {len(filas)} restricciones. Esto es esperable: con X y Z fijas, la fila")
            emitir("    de capacidad no tiene variables libres y Z no aparece en el objetivo (1), que solo")
            emitir("    depende de X. El PL fijo no puede reasignar clientes entre rutas, por lo que no")
            emitir("    captura el costo de la capacidad; no implica que Q sea irrelevante en el MIP.")
        else:
            emitir(f"  - {len(con_precio)} restricción(es) con Pi != 0: " +
                   ", ".join(f"capacidad[{r},{t}] (Pi = {pi:.3f})" for r, t, pi in con_precio) + ".")
            emitir("    En ellas, +1 unidad de Q cambia la distancia en Pi mientras Q esté en su rango.")
 
        if activas:
            emitir(f"  - Restricciones activas (Slack = 0, {len(activas)} de {len(filas)}): " +
                   ", ".join(f"capacidad[{r},{t}]" for r, t in activas) + ".")
        else:
            emitir(f"  - Ninguna restricción de capacidad está activa (de {len(filas)}).")
            if not base_optima:
                emitir("    (Cuidado: es una incumbente; el óptimo podría tener rutas llenas.)")
 
        if rangos_finitos_up:
            emitir("  - SARHSUp finito en: " +
                   ", ".join(f"capacidad[{r},{t}] (hasta {up:.1f})" for r, t, up in rangos_finitos_up) +
                   "; más allá de ese valor cambia la base óptima del PL fijo.")
        else:
            emitir("  - SARHSUp = +inf en todas: Q puede aumentar sin límite sin alterar la solución fija.")
 
        emitir(f"  - La asignación actual (Z) sigue siendo factible mientras Q >= {carga_max:.0f} "
               f"(máxima carga, en capacidad[{r_max},{t_max}]).")
        emitir(f"    Con Q = {Q} la holgura mínima es {Q - carga_max:.0f} ({100*(Q - carga_max)/Q:.1f} % de Q).")
 
# ---------- Guardado ----------
os.makedirs("resultados", exist_ok=True)
salida = os.path.join("resultados", f"sensibilidad_{d['nombre']}.txt")
with open(salida, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas) + "\n")
print(f"\nResultados guardados en {salida}")