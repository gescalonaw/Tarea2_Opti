# -*- coding: utf-8 -*-
"""
Lectura de instancias, rutas y validacion independiente del solver.
Lo usan modelo_gurobi.py, modelo_cplex.py y los scripts de corrida.
"""
import json
import os


def leer_instancia(archivo):
    """Lee el JSON de la instancia y arma los conjuntos del modelo.

    Nodos: 0 = deposito (salida), 1..n = clientes, n+1 = deposito (retorno).
    Dias t = 0..T-1 y rutas r = 0..R-1.
    """
    with open(archivo, encoding='utf-8') as f:
        datos = json.load(f)
    n, T, R = datos['n'], datos['D'], datos['R']
    clientes = datos['clientes']
    d = dict(nombre=datos.get('nombre', os.path.splitext(os.path.basename(archivo))[0]),
             n=n, T=T, R=R, Q=datos['Q'], aW=datos['aW'], bW=datos['bW'],
             dist=datos['td'], tv=datos['tt'])

    def por_dia(v):
        return list(v) if isinstance(v, list) else [v] * T

    d['q'] = [[0] * T] + [por_dia(c['q_dia']) for c in clientes] + [[0] * T]
    d['s'] = [[0] * T] + [por_dia(c.get('st', 0)) for c in clientes] + [[0] * T]
    d['a'] = [0] * (n + 2)
    d['b'] = [0] * (n + 2)
    d['con_ventana'] = []
    for i, c in enumerate(clientes, start=1):
        if c.get('tiene_ventana'):
            d['a'][i], d['b'][i] = c['a'], c['b']
            d['con_ventana'].append(i)
    d['xy'] = [None] + [(c['x'], c['y']) for c in clientes] + [None]

    # Conjuntos
    d['C'] = list(range(1, n + 1))
    d['O'] = [(i, t) for t in range(T) for i in d['C'] if d['q'][i][t] > 0]
    d['Ct'] = {t: [i for i in d['C'] if d['q'][i][t] > 0] for t in range(T)}   # clientes con pedido el dia t
    # Arcos validos del dia t (como en el paper): deposito <-> clientes con pedido,
    # clientes con pedido entre si, y el arco directo 0 -> n+1 (ruta vacia, costo 0).
    d['A'] = {}
    for t in range(T):
        Ct = d['Ct'][t]
        arcos = [(0, j) for j in Ct] + [(0, n + 1)]
        arcos += [(i, j) for i in Ct for j in Ct if i != j]
        arcos += [(i, n + 1) for i in Ct]
        d['A'][t] = arcos
    d['claves_X'] = [(r, i, j, t) for r in range(R) for t in range(T) for (i, j) in d['A'][t]]

    # Big-M de la TC2: horizonte + servicio maximo + viaje maximo
    d['M'] = (d['bW'] - d['aW']) + max(max(f) for f in d['s']) + max(max(f) for f in d['tv'])
    return d


def extraer_rutas(d, valor):
    """Devuelve rutas[t][r] = [clientes en orden], siguiendo los arcos con X = 1."""
    n = d['n']
    usados = {(r, i, j, t) for (r, i, j, t) in d['claves_X'] if valor((r, i, j, t)) > 0.5}
    rutas = []
    for t in range(d['T']):
        por_ruta = []
        for r in range(d['R']):
            sig = {i: j for (rr, i, j, tt) in usados if rr == r and tt == t}
            camino, actual = [], 0
            while actual in sig and sig[actual] != n + 1 and len(camino) <= n:
                actual = sig[actual]
                camino.append(actual)
            por_ruta.append(camino)
        rutas.append(por_ruta)
    return rutas


def validar(d, rutas):
    """Chequeo independiente del solver. Devuelve (distancia recalculada, lista de problemas)."""
    n, Q, q, s, tv, dist = d['n'], d['Q'], d['q'], d['s'], d['tv'], d['dist']
    problemas, total, ruta_de = [], 0.0, {}
    for t in range(d['T']):
        visitados = []
        for r in range(d['R']):
            camino = rutas[t][r]
            visitados += camino
            nodos = [0] + camino + [n + 1]
            total += sum(dist[a][b] for a, b in zip(nodos, nodos[1:]))
            carga = sum(q[i][t] for i in camino)
            if carga > Q + 1e-6:
                problemas.append(f'dia {t+1} ruta {r+1}: carga {carga} > Q={Q}')
            # simulacion de horarios saliendo a la apertura (salida mas temprana = dominante)
            hora = d['aW']
            for a_, b_ in zip(nodos, nodos[1:]):
                hora += (s[a_][t] if a_ != 0 else 0) + tv[a_][b_]
                if b_ != n + 1 and b_ in d['con_ventana']:
                    hora = max(hora, d['a'][b_])
                    if hora > d['b'][b_] + 1e-6:
                        problemas.append(f'dia {t+1} ruta {r+1}: cliente {b_} llega {hora:.1f} > b={d["b"][b_]}')
            if hora > d['bW'] + 1e-6:
                problemas.append(f'dia {t+1} ruta {r+1}: vuelve {hora:.1f} > cierre {d["bW"]}')
            for i in camino:
                if ruta_de.setdefault(i, r) != r:
                    problemas.append(f'cliente {i}: cambia de ruta (consistencia)')
        esperados = sorted(d['Ct'][t])
        if sorted(visitados) != esperados:
            faltan = sorted(set(esperados) - set(visitados))
            sobran = sorted(set(visitados) - set(esperados))
            problemas.append(f'dia {t+1}: faltan {faltan}, sobran/no piden {sobran}, repetidos={len(visitados) != len(set(visitados))}')
    return total, problemas


def fmt(x, dec=2):
    return '-' if x is None else (f'{x:.{dec}f}' if isinstance(x, float) else str(x))
