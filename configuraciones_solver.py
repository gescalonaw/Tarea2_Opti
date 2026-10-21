import os
from modelo import leer_instancia, armar_modelo

INSTANCIA = "generador/data/instancias/instancia_A_Gabi.json"
TIME_LIMIT = 600

configuraciones = [
    ("Base",         {}),
    ("Cuts=0",       {"Cuts": 0}),
    ("Presolve=0",   {"Presolve": 0}),
    ("MIPFocus=1",   {"MIPFocus": 1}),
    ("MIPFocus=3",   {"MIPFocus": 3}),
    ("Heuristics=0", {"Heuristics": 0}),
]

d = leer_instancia(INSTANCIA)
resultados = []

for nombre, params in configuraciones:
    m, X, Z, W, cap = armar_modelo(d)   # modelo nuevo en cada corrida
    m.Params.Threads = 1
    m.Params.TimeLimit = TIME_LIMIT
    for p, v in params.items():
        setattr(m.Params, p, v)         # equivalente a m.Params.Cuts = 0, etc.

    m.optimize()

    fila = {
        "configuracion": nombre,
        "objetivo": m.ObjVal if m.SolCount > 0 else None,
        "gap_%": 100 * m.MIPGap if m.SolCount > 0 else None,
        "tiempo_s": m.Runtime,
    }
    resultados.append(fila)
    print(f"{nombre:15s} | obj={fila['objetivo']:.1f} | gap={fila['gap_%']:.2f}% | tiempo={fila['tiempo_s']:.1f}s")

os.makedirs("resultados", exist_ok=True)
with open("resultados/configuraciones_solver.txt", "w", encoding="utf-8") as f:
    f.write(f"Instancia: {d['nombre']}\n\n")
    for fila in resultados:
        f.write(f"{fila['configuracion']:15s} | obj={fila['objetivo']:.1f} | gap={fila['gap_%']:.2f}% | tiempo={fila['tiempo_s']:.1f}s\n")

print("\nResultados guardados en resultados/configuraciones_solver.txt")