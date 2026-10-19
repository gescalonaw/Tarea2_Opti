# -*- coding: utf-8 -*-
"""
Corre el modelo reducido ConRVP-SLA sobre una instancia (instancia_A.json o
instancia_B.json), muestra el resultado y lo guarda en resultados/<nombre>.txt

Uso (desde la raiz del repo):
    python resolver.py generador/data/instancias/instancia_A.json
    python resolver.py generador/data/instancias/instancia_B.json
    python resolver.py generador/data/instancias/instancia_A.json 60   # 60 s, prueba rapida
"""
import os
import sys

from modelo import leer_instancia, armar_modelo

archivo = sys.argv[1] if len(sys.argv) > 1 else "generador/data/instancias/instancia_A.json"
LIMITE = float(sys.argv[2]) if len(sys.argv) > 2 else 600  # segundos (enunciado: 600)

d = leer_instancia(archivo)
linea0 = f"Instancia: {d['nombre']} | clientes = {d['n']} | dias = {d['T']} | rutas = {d['R']} | Q = {d['Q']}"
print(linea0)

m, X, Z, W, cap = armar_modelo(d)
m.Params.OutputFlag = 1   # ver el log de Gurobi mientras resuelve
m.Params.Threads = 1
m.Params.TimeLimit = LIMITE
m.optimize()

lineas = [linea0]

if m.SolCount == 0:
    linea = f"Sin solucion dentro del limite de tiempo. Estado: {m.Status}"
    print(linea)
    lineas.append(linea)
else:
    linea = f"Distancia total = {m.ObjVal:.1f} | gap = {100*m.MIPGap:.2f} % | tiempo = {m.Runtime:.1f} s"
    print(linea)
    lineas.append(linea)
    lineas.append("")

    n, Q, q = d['n'], d['Q'], d['q']
    for t in range(d['T']):
        for r in range(d['R']):
            actual = 0
            camino = []
            while actual != n + 1:
                siguiente = None
                for j in range(n + 2):
                    if (r, actual, j, t) in X and X[r, actual, j, t].X > 0.5:
                        siguiente = j
                        break
                if siguiente is None:
                    break
                actual = siguiente
                if actual != n + 1:
                    camino.append(actual)
            carga = sum(q[i][t] for i in camino)
            texto = ' -> '.join(f'{i}(llega {W[i, t].X:.0f})' for i in camino) if camino else 'vacia'
            linea = f"Dia {t+1} | Ruta {r+1} | carga {carga}/{Q} | D -> {texto} -> D"
            print(linea)
            lineas.append(linea)

os.makedirs("resultados", exist_ok=True)
salida = os.path.join("resultados", f"{d['nombre']}.txt")
with open(salida, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas) + "\n")
print(f"\nResultados guardados en {salida}")