# -*- coding: utf-8 -*-
"""
Funciones comunes de los scripts de corrida (relajacion.py, entero.py, correr_todo.py).

Sigue el notebook de apoyo de la TC3 (Comparacion_Gurobi_vs_CPLEX.ipynb):
  - lo unico que se fija igual en ambos solvers es el limite de tiempo;
  - para cada instancia se resuelve la relajacion y luego el entero, en los dos solvers;
  - se anotan 4 numeros: objetivo, tiempo, nodos y gap final
      Gurobi: m.ObjVal, m.Runtime, m.NodeCount, m.MIPGap
      CPLEX:  sol.objective_value, solve_details.time, nb_nodes_processed, mip_relative_gap
  - se imprime la diferencia de objetivo Gurobi-CPLEX por tipo (relajacion / entero).
"""
import csv
import json
import os
import statistics
import time

from datos import fmt, validar

SOLVERS = ('gurobi', 'cplex')
NOMBRE = {'gurobi': 'Gurobi', 'cplex': 'CPLEX'}
OPTIMO = {'OPTIMAL', 'integer optimal solution', 'integer optimal, tolerance'}


def _modulo(solver):
    if solver == 'gurobi':
        import modelo_gurobi as mod
    else:
        import modelo_cplex as mod
    return mod


def solvers_a_correr(solo):
    return [s for s in SOLVERS if solo in (None, s)]


def correr_relajacion(d, solvers, carpeta_logs, repeticiones=1):
    """Relajacion continua en cada solver. Como el LP tarda milisegundos y un solo tiempo
    es ruidoso, se puede repetir y se reporta el tiempo promedio."""
    res = {}
    for s in solvers:
        tiempos = []
        for _ in range(repeticiones):
            r = _modulo(s).relajacion(d, carpeta_logs)
            tiempos.append(r['tiempo'])
        r['tiempo'] = statistics.mean(tiempos)
        r['tiempo_desv'] = statistics.pstdev(tiempos) if len(tiempos) > 1 else 0.0
        r['repeticiones'] = repeticiones
        extra = f' (promedio de {repeticiones}, desv. {r["tiempo_desv"]:.4f})' if repeticiones > 1 else ''
        print(f"[{s}] relajacion: z_LP={fmt(r['obj'], 4)} | {r['tiempo']:.4f} s{extra} | {r['estado']}")
        res[s] = r
    _diferencia('Relajacion', res)
    return res


def correr_entero(d, solvers, carpeta, time_limit, threads, verbose):
    """Modelo entero en cada solver + validacion independiente de cada solucion."""
    res = {}
    for s in solvers:
        t0 = time.time()
        r = _modulo(s).entero(d, os.path.join(carpeta, 'logs'), time_limit, threads, verbose)
        r['tiempo_pared'] = time.time() - t0
        print(f"[{s}] entero: z={fmt(r['obj'], 4)} | cota={fmt(r['cota'], 4)} | gap={fmt(r['gap'], 4)}% | "
              f"nodos={r['nodos']} | {r['tiempo']:.2f} s | {r['estado']} "
              f"({r['vars']} vars, {r['binarias']} binarias, {r['restricciones']} restricciones)")
        r['distancia_validada'], r['problemas'] = None, ['sin solucion entera']
        if r['rutas'] is not None:
            r['distancia_validada'], r['problemas'] = validar(d, r['rutas'])
            print(f"[{s}] validacion: distancia recalculada={r['distancia_validada']:.4f} | "
                  + ('OK' if not r['problemas'] else f"{len(r['problemas'])} problemas: " + '; '.join(r['problemas'][:5])))
            with open(os.path.join(carpeta, f"{d['nombre']}_{s}_rutas.json"), 'w') as f:
                json.dump(dict(instancia=d['nombre'], solver=s, obj=r['obj'], rutas=r['rutas']), f, indent=1)
        res[s] = r
    _diferencia('Entero', res)
    if len(res) == 2 and not all(r['estado'] in OPTIMO for r in res.values()):
        print('   Ojo: al menos un solver corto por tiempo (gap > 0): el optimo no esta probado y los '
              'objetivos pueden diferir. Comparar cota y gap.')
    return res


def _diferencia(tipo, res):
    if len(res) == 2 and None not in (res['gurobi']['obj'], res['cplex']['obj']):
        dif = abs(res['gurobi']['obj'] - res['cplex']['obj'])
        print(f'{tipo}: diferencia de objetivo Gurobi-CPLEX = {dif:.3e}')


def filas(d, tipo, res):
    """Filas en el formato del notebook de apoyo: tipo, solver, objetivo, tiempo_s, nodos, gap."""
    out = []
    for s, r in res.items():
        fila = dict(instancia=d['nombre'], tipo=tipo, solver=NOMBRE[s], objetivo=r['obj'],
                    tiempo_s=r['tiempo'], nodos=r['nodos'],
                    gap=(r['gap'] / 100 if tipo == 'Entero' and r['gap'] is not None else r['gap']),
                    estado=r['estado'])
        if tipo == 'Entero':
            fila.update(cota=r['cota'], solucion_valida=not r['problemas'], tiempo_pared_s=r['tiempo_pared'],
                        variables=r['vars'], binarias=r['binarias'], restricciones=r['restricciones'])
        else:
            fila.update(repeticiones=r['repeticiones'], tiempo_desv_s=r['tiempo_desv'])
        out.append(fila)
    return out


def guardar_tabla(todas, carpeta, nombre, encabezado=''):
    """Guarda la tabla larga (una fila por instancia, tipo y solver) en .csv y .txt."""
    if not todas:
        return
    todas = sorted(todas, key=lambda f: (f['instancia'], f['tipo'] != 'Relajación', f['solver']))
    campos = []
    for f in todas:
        campos += [k for k in f if k not in campos]
    with open(os.path.join(carpeta, nombre + '.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(todas)
    cols = [('instancia', 0), ('tipo', 0), ('solver', 0), ('objetivo', 4), ('tiempo_s', 4), ('nodos', 0),
            ('gap', 6), ('cota', 4), ('estado', 0), ('solucion_valida', 0)]
    lineas = [' | '.join(c for c, _ in cols)]
    for f in todas:
        lineas.append(' | '.join(fmt(f.get(c), dec) if isinstance(f.get(c), float)
                                 else ('-' if f.get(c) is None else str(f.get(c))) for c, dec in cols))
    texto = '\n'.join(lineas)
    with open(os.path.join(carpeta, nombre + '.txt'), 'w', encoding='utf-8') as fh:
        fh.write((encabezado + '\n' if encabezado else '') + texto + '\n')
    print('\n' + texto + f"\n\nGuardado en {os.path.join(carpeta, nombre)}.txt / .csv")
