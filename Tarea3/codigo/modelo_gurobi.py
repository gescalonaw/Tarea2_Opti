# -*- coding: utf-8 -*-
"""
Modelo conVRP-SLA reducido (corregido) en Gurobi.

  construir(d)                          -> modelo entero (m, X, Z)
  relajacion(d, carpeta_logs)           -> relajacion continua con Model.relax()
  entero(d, carpeta_logs, time_limit, threads=0, verbose=False)
"""
import os

from datos import extraer_rutas


def construir(d):
    import gurobipy as gp
    from gurobipy import GRB

    n, T, R, Q, M = d['n'], d['T'], d['R'], d['Q'], d['M']
    dist, tv, q, s, a, b = d['dist'], d['tv'], d['q'], d['s'], d['a'], d['b']
    O, Ct, Ru, D = d['O'], d['Ct'], range(R), range(T)
    entra = {(j, t): [i for (i, k) in d['A'][t] if k == j] for (j, t) in O}
    sale = {(j, t): [k for (i, k) in d['A'][t] if i == j] for (j, t) in O}

    m = gp.Model(d['nombre'])
    m.Params.LogToConsole = 0   # el log va al archivo (LogFile) que se fija antes de resolver
    X = m.addVars(d['claves_X'], vtype=GRB.BINARY, name='X')
    Z = m.addVars(d['C'], Ru, vtype=GRB.BINARY, name='Z')
    W = m.addVars(O, lb=d['aW'], ub=d['bW'], name='W')
    dW = m.addVars(Ru, name='dW')
    rW = m.addVars(Ru, D, name='rW')

    # (1) objetivo
    m.setObjective(gp.quicksum(dist[i][j] * X[r, i, j, t] for (r, i, j, t) in d['claves_X']), GRB.MINIMIZE)
    # (2) asignacion cliente-ruta (consistencia)
    m.addConstrs((Z.sum(i, '*') == 1 for i in d['C']), name='asignacion')
    # (3)-(4) flujo/grado solo para clientes con pedido ese dia
    m.addConstrs((gp.quicksum(X[r, i, j, t] for i in entra[j, t]) == Z[j, r]
                  for (j, t) in O for r in Ru), name='entrada')
    m.addConstrs((gp.quicksum(X[r, j, k, t] for k in sale[j, t]) == Z[j, r]
                  for (j, t) in O for r in Ru), name='salida')
    # (5) cada ruta sale una vez del deposito cada dia
    m.addConstrs((gp.quicksum(X[r, 0, j, t] for j in Ct[t] + [n + 1]) == 1
                  for r in Ru for t in D), name='sale_deposito')
    # (7) secuenciacion temporal (Big-M)
    m.addConstrs((W[i, t] + s[i][t] + tv[i][j] <= W[j, t] + M * (1 - X[r, i, j, t])
                  for t in D for i in Ct[t] for j in Ct[t] if i != j for r in Ru), name='tiempo')
    # (8) ventanas de tiempo, solo para pedidos de clientes con ventana
    m.addConstrs((W[i, t] >= a[i] for (i, t) in O if i in d['con_ventana']), name='ventana_ini')
    m.addConstrs((W[i, t] <= b[i] for (i, t) in O if i in d['con_ventana']), name='ventana_fin')
    # (9) deposito -> primer cliente
    m.addConstrs((dW[r] + tv[0][j] <= W[j, t] + M * (1 - X[r, 0, j, t])
                  for t in D for j in Ct[t] for r in Ru), name='salida_W')
    # (10) ultimo cliente -> deposito
    m.addConstrs((W[i, t] + s[i][t] + tv[i][n + 1] <= rW[r, t] + M * (1 - X[r, i, n + 1, t])
                  for t in D for i in Ct[t] for r in Ru), name='retorno_W')
    # ruta vacia: el retorno no es antes de la salida
    m.addConstrs((dW[r] <= rW[r, t] + M * (1 - X[r, 0, n + 1, t]) for r in Ru for t in D), name='ruta_vacia')
    # (11)-(12) horario del deposito
    m.addConstrs((dW[r] >= d['aW'] for r in Ru), name='abre')
    m.addConstrs((rW[r, t] <= d['bW'] for r in Ru for t in D), name='cierra')
    # (14) capacidad
    m.addConstrs((gp.quicksum(q[i][t] * Z[i, r] for i in Ct[t]) <= Q for r in Ru for t in D), name='capacidad')
    m.update()
    return m, X, Z


ESTADO_GRB = {2: 'OPTIMAL', 3: 'INFEASIBLE', 9: 'TIME_LIMIT', 5: 'UNBOUNDED', 4: 'INF_OR_UNBD', 11: 'INTERRUPTED'}


def relajacion(d, carpeta_logs):
    """Relajacion continua: m.update() y luego m.relax() (X y Z continuas en [0, 1])."""
    m, X, Z = construir(d)
    m.update()
    mr = m.relax()
    mr.Params.LogFile = os.path.join(carpeta_logs, f"{d['nombre']}_gurobi_relajacion.log")
    mr.Params.OutputFlag = 1
    mr.Params.LogToConsole = 0
    mr.optimize()
    return dict(estado=ESTADO_GRB.get(mr.Status, str(mr.Status)),
                obj=mr.ObjVal if mr.Status == 2 else None, tiempo=mr.Runtime,
                nodos=0, gap=0.0)


def entero(d, carpeta_logs, time_limit, threads=0, verbose=False):
    """Modelo entero con la configuracion por defecto (solo se fija el limite de tiempo)."""
    m, X, Z = construir(d)
    m.Params.LogFile = os.path.join(carpeta_logs, f"{d['nombre']}_gurobi_entero.log")
    m.Params.LogToConsole = 1 if verbose else 0
    m.Params.TimeLimit = time_limit
    if threads > 0:
        m.Params.Threads = threads
    m.optimize()
    res = dict(estado=ESTADO_GRB.get(m.Status, str(m.Status)), tiempo=m.Runtime,
               nodos=int(m.NodeCount), cota=m.ObjBound, obj=None, gap=None, rutas=None,
               vars=m.NumVars, binarias=m.NumBinVars, restricciones=m.NumConstrs)
    if m.SolCount > 0:
        res['obj'] = m.ObjVal
        res['gap'] = 100 * m.MIPGap
        res['rutas'] = extraer_rutas(d, lambda k: X[k].X)
    return res
