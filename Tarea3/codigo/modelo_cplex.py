# -*- coding: utf-8 -*-
"""
Modelo conVRP-SLA reducido (corregido) en CPLEX (docplex). Mismas ecuaciones que modelo_gurobi.py.

  construir(d)                          -> modelo entero (mdl, X, Z)
  relajacion(d, carpeta_logs)           -> relajacion continua con LinearRelaxer (binarias -> continuas)
  entero(d, carpeta_logs, time_limit, threads=0, verbose=False)
"""
import os
import sys

from datos import extraer_rutas


def construir(d):
    """Mismo modelo que modelo_gurobi.construir."""
    from docplex.mp.model import Model

    n, T, R, Q, M = d['n'], d['T'], d['R'], d['Q'], d['M']
    dist, tv, q, s, a, b = d['dist'], d['tv'], d['q'], d['s'], d['a'], d['b']
    O, Ct, Ru, D = d['O'], d['Ct'], range(R), range(T)
    entra = {(j, t): [i for (i, k) in d['A'][t] if k == j] for (j, t) in O}
    sale = {(j, t): [k for (i, k) in d['A'][t] if i == j] for (j, t) in O}

    mdl = Model(name=d['nombre'])
    claves_Z = [(i, r) for i in d['C'] for r in Ru]
    X = mdl.binary_var_dict(d['claves_X'], name='X')
    Z = mdl.binary_var_dict(claves_Z, name='Z')
    W = mdl.continuous_var_dict(O, lb=d['aW'], ub=d['bW'], name='W')
    dW = mdl.continuous_var_dict(list(Ru), lb=0, name='dW')
    rW = mdl.continuous_var_dict([(r, t) for r in Ru for t in D], lb=0, name='rW')

    # (1)
    mdl.minimize(mdl.sum(dist[i][j] * X[r, i, j, t] for (r, i, j, t) in d['claves_X']))
    # (2)
    mdl.add_constraints((mdl.sum(Z[i, r] for r in Ru) == 1 for i in d['C']),
                        names=(f'asignacion_{i}' for i in d['C']))
    # (3)-(4)
    for (j, t) in O:
        for r in Ru:
            mdl.add_constraint(mdl.sum(X[r, i, j, t] for i in entra[j, t]) == Z[j, r], f'entrada_{j}_{t}_{r}')
            mdl.add_constraint(mdl.sum(X[r, j, k, t] for k in sale[j, t]) == Z[j, r], f'salida_{j}_{t}_{r}')
    # (5)
    for r in Ru:
        for t in D:
            mdl.add_constraint(mdl.sum(X[r, 0, j, t] for j in Ct[t] + [n + 1]) == 1, f'sale_deposito_{r}_{t}')
    # (7)
    for t in D:
        for i in Ct[t]:
            for j in Ct[t]:
                if i != j:
                    for r in Ru:
                        mdl.add_constraint(W[i, t] + s[i][t] + tv[i][j] <= W[j, t] + M * (1 - X[r, i, j, t]),
                                           f'tiempo_{r}_{i}_{j}_{t}')
    # (8)
    for (i, t) in O:
        if i in d['con_ventana']:
            mdl.add_constraint(W[i, t] >= a[i], f'ventana_ini_{i}_{t}')
            mdl.add_constraint(W[i, t] <= b[i], f'ventana_fin_{i}_{t}')
    # (9)-(10)
    for t in D:
        for i in Ct[t]:
            for r in Ru:
                mdl.add_constraint(dW[r] + tv[0][i] <= W[i, t] + M * (1 - X[r, 0, i, t]), f'salida_W_{r}_{i}_{t}')
                mdl.add_constraint(W[i, t] + s[i][t] + tv[i][n + 1] <= rW[r, t] + M * (1 - X[r, i, n + 1, t]),
                                   f'retorno_W_{r}_{i}_{t}')
    # ruta vacia
    for r in Ru:
        for t in D:
            mdl.add_constraint(dW[r] <= rW[r, t] + M * (1 - X[r, 0, n + 1, t]), f'ruta_vacia_{r}_{t}')
    # (11)-(12)
    for r in Ru:
        mdl.add_constraint(dW[r] >= d['aW'], f'abre_{r}')
        for t in D:
            mdl.add_constraint(rW[r, t] <= d['bW'], f'cierra_{r}_{t}')
    # (14)
    for r in Ru:
        for t in D:
            mdl.add_constraint(mdl.sum(q[i][t] * Z[i, r] for i in Ct[t]) <= Q, f'capacidad_{r}_{t}')
    return mdl, X, Z


class _Tee:
    """Escribe el log del solver en un archivo y, opcionalmente, en pantalla."""

    def __init__(self, ruta, pantalla):
        self.f = open(ruta, 'w', encoding='utf-8')
        self.pantalla = pantalla

    def write(self, texto):
        self.f.write(texto)
        if self.pantalla:
            sys.stdout.write(texto)

    def flush(self):
        self.f.flush()

    def close(self):
        self.f.close()


def relajacion(d, carpeta_logs):
    """Relajacion continua: LinearRelaxer pasa las binarias X y Z a continuas en [0, 1]
    (igual que en el notebook de apoyo de la TC3)."""
    from docplex.mp.relax_linear import LinearRelaxer
    mdl, X, Z = construir(d)
    rel = LinearRelaxer.make_relaxed_model(mdl)
    log = _Tee(os.path.join(carpeta_logs, f"{d['nombre']}_cplex_relajacion.log"), False)
    sol = rel.solve(log_output=log)
    log.close()
    sd = rel.solve_details
    return dict(estado=sd.status, obj=sol.objective_value if sol else None, tiempo=sd.time,
                nodos=0, gap=0.0)


def entero(d, carpeta_logs, time_limit, threads=0, verbose=False):
    """Modelo entero con la configuracion por defecto (solo se fija el limite de tiempo)."""
    mdl, X, Z = construir(d)
    mdl.parameters.timelimit = time_limit
    if threads > 0:
        mdl.parameters.threads = threads
    log = _Tee(os.path.join(carpeta_logs, f"{d['nombre']}_cplex_entero.log"), verbose)
    sol = mdl.solve(log_output=log)
    log.close()
    sd = mdl.solve_details
    stats = mdl.statistics
    res = dict(estado=sd.status, tiempo=sd.time, nodos=int(sd.nb_nodes_processed),
               cota=sd.best_bound, obj=None, gap=None, rutas=None,
               vars=stats.number_of_variables, binarias=stats.number_of_binary_variables,
               restricciones=stats.number_of_constraints)
    if sol is not None:
        res['obj'] = sol.objective_value
        res['gap'] = 100 * sd.mip_relative_gap
        res['rutas'] = extraer_rutas(d, lambda k: sol.get_value(X[k]))
    return res
