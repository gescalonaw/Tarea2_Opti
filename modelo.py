# -*- coding: utf-8 -*-
"""
Modelo reducido ConRVP-SLA (Campelo et al., 2019) con gurobipy.

Contiene:
  leer_instancia(archivo)      lee el JSON y arma las listas/matrices del problema
  armar_modelo(d)              crea el modelo (variables, funcion objetivo y restricciones)
  mostrar_rutas(d, m, X, W)    imprime las rutas de la solucion

Nodos: 0 = deposito (salida), 1..n = clientes, n+1 = deposito (retorno).
Los indices parten en 0: dia 1 = t=0, ruta 1 = r=0.

Lee el formato de instancia que genera el script 
(carpeta generador/): un JSON con n, D, R, Q, aW, bW,
clientes (con q_dia, st, a/b, tiene_ventana) y las matrices td/tt ya
calculadas. Es el formato de instancias/instancia_A.json e instancia_B.json.
"""
import json
import gurobipy as gp
from gurobipy import GRB


def leer_instancia(archivo):
    """Lee una instancia en el formato de instancia_A.json / instancia_B.json
    (generador del compañero): n, D, R, Q, aW, bW, clientes con
    q_dia/st/a/b/tiene_ventana, y las matrices td/tt ya calculadas.
    """
    with open(archivo, encoding='utf-8') as f:
        datos = json.load(f)

    d = {}
    d['nombre'] = datos.get('nombre', 'instancia')
    n = datos['n']
    T = datos['D']
    R = datos['R']
    d['n'], d['T'], d['R'] = n, T, R
    d['Q'] = datos['Q']
    d['apertura'] = datos['aW']
    d['cierre'] = datos['bW']

    d['dist'] = datos['td']
    d['tv'] = datos['tt']

    clientes = datos['clientes']

    def por_dia(valor):
        if isinstance(valor, list):
            return valor
        return [valor] * T

    d['q'] = [[0] * T] + [por_dia(c['q_dia']) for c in clientes] + [[0] * T]
    d['s'] = [[0] * T] + [por_dia(c.get('st', 0)) for c in clientes] + [[0] * T]

    # ventanas de tiempo [a_i, b_i] (solo algunos clientes tienen)
    d['a'] = [0] * (n + 2)
    d['b'] = [0] * (n + 2)
    d['con_ventana'] = []
    for i, c in enumerate(clientes, start=1):
        if c.get('tiene_ventana'):
            d['a'][i], d['b'][i] = c['a'], c['b']
            d['con_ventana'].append(i)

    # Big-M: una constante suficientemente grande
    d['M'] = (d['cierre'] - d['apertura']) + max(max(fila) for fila in d['s']) + max(max(fila) for fila in d['tv'])
    return d


def armar_modelo(d):
    # --- datos de la instancia ---
    n, T, R, Q, M = d['n'], d['T'], d['R'], d['Q'], d['M']
    apertura, cierre = d['apertura'], d['cierre']
    dist, tv, q, s, a, b = d['dist'], d['tv'], d['q'], d['s'], d['a'], d['b']
    con_ventana = d['con_ventana']

    # --- conjuntos ---
    N = range(n + 2)       # todos los nodos
    Cl = range(1, n + 1)   # clientes
    D = range(T)           # dias
    Ru = range(R)          # rutas

    m = gp.Model(d['nombre'])
    m.Params.OutputFlag = 0

    # Arcos permitidos: salir del deposito, entre clientes, volver al deposito
    A = [(0, j) for j in Cl] + [(0, n + 1)]
    A += [(i, j) for i in Cl for j in Cl if i != j]
    A += [(i, n + 1) for i in Cl]

    # ---------- Variables (16) ----------
    X = m.addVars([(r, i, j, t) for r in Ru for (i, j) in A for t in D], vtype=GRB.BINARY, name='X')
    Z = m.addVars(Cl, Ru, vtype=GRB.BINARY, name='Z')
    W = m.addVars(Cl, D, lb=apertura, ub=cierre, name='W')
    dW = m.addVars(Ru, name='dW')
    rW = m.addVars(Ru, D, name='rW')

    # ---------- Funcion objetivo (1) ----------
    m.setObjective(gp.quicksum(dist[i][j] * X[r, i, j, t] for r in Ru for (i, j) in A for t in D), GRB.MINIMIZE)

    # ---------- Restricciones ----------
    # (2) cada cliente pertenece a exactamente una ruta
    m.addConstrs((Z.sum(i, '*') == 1 for i in Cl), name='asignacion')

    # (3) si el cliente j esta en la ruta r, entra un arco a j
    m.addConstrs((gp.quicksum(X[r, i, j, t] for i in N if (i, j) in A) == Z[j, r]
                  for j in Cl for r in Ru for t in D), name='entrada')

    # (4) si el cliente j esta en la ruta r, sale un arco de j
    m.addConstrs((gp.quicksum(X[r, j, k, t] for k in N if (j, k) in A) == Z[j, r]
                  for j in Cl for r in Ru for t in D), name='salida')

    # (5) cada ruta sale una vez del deposito cada dia
    m.addConstrs((gp.quicksum(X[r, 0, j, t] for j in N if (0, j) in A) == 1
                  for r in Ru for t in D), name='sale_deposito')

    # (7) tiempo de llegada entre dos clientes (Big-M)
    m.addConstrs((W[i, t] + s[i][t] + tv[i][j] <= W[j, t] + M * (1 - X[r, i, j, t])
                  for r in Ru for i in Cl for j in Cl if i != j for t in D), name='tiempo')

    # (8) ventanas de tiempo (solo clientes con ventana)
    m.addConstrs((W[i, t] >= a[i] for i in con_ventana for t in D), name='ventana_ini')
    m.addConstrs((W[i, t] <= b[i] for i in con_ventana for t in D), name='ventana_fin')

    # (9) salida del deposito -> primer cliente
    m.addConstrs((dW[r] + tv[0][j] <= W[j, t] + M * (1 - X[r, 0, j, t])
                  for r in Ru for j in Cl for t in D), name='salida_W')

    # (10) ultimo cliente -> retorno al deposito
    m.addConstrs((W[i, t] + s[i][t] + tv[i][n + 1] <= rW[r, t] + M * (1 - X[r, i, n + 1, t])
                  for r in Ru for i in Cl for t in D), name='retorno_W')

    # ruta vacia: el retorno no puede ser antes de la salida
    m.addConstrs((dW[r] <= rW[r, t] + M * (1 - X[r, 0, n + 1, t])
                  for r in Ru for t in D), name='ruta_vacia')

    # (11) y (12) horario del deposito
    m.addConstrs((dW[r] >= apertura for r in Ru), name='abre')
    m.addConstrs((rW[r, t] <= cierre for r in Ru for t in D), name='cierra')

    # (14) capacidad del vehiculo
    cap = m.addConstrs((gp.quicksum(q[i][t] * Z[i, r] for i in Cl) <= Q
                        for r in Ru for t in D), name='capacidad')

    return m, X, Z, W, cap


def mostrar_rutas(d, m, X, W):
    """Imprime la ruta de cada dia siguiendo los arcos con X = 1."""
    n, Q, q = d['n'], d['Q'], d['q']
    for t in range(d['T']):
        for r in range(d['R']):
            actual = 0
            camino = []
            while actual != n + 1:
                for j in range(n + 2):
                    if (r, actual, j, t) in X and X[r, actual, j, t].X > 0.5:
                        actual = j
                        break
                if actual != n + 1:
                    camino.append(actual)
            carga = sum(q[i][t] for i in camino)
            texto = ' -> '.join(f'{i}(llega {W[i, t].X:.0f})' for i in camino) if camino else 'vacia'
            print(f'Dia {t+1} | Ruta {r+1} | carga {carga}/{Q} | D -> {texto} -> D')
