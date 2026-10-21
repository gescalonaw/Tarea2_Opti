from modelo import leer_instancia, armar_modelo

d = leer_instancia("generador/data/instancias/instancia_A_Gabi.json")
m, X, Z, W, cap = armar_modelo(d)

m.Params.Threads = 1
m.Params.TimeLimit = 600
m.optimize()
z_estrella = m.ObjVal

m_lp = m.relax()
m_lp.optimize()
z_lp = m_lp.ObjVal

brecha = 100 * (z_estrella - z_lp) / z_estrella
print(f"z_LP = {z_lp:.2f} | z* = {z_estrella:.2f} | brecha de integralidad = {brecha:.2f} %")