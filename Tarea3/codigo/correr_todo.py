# -*- coding: utf-8 -*-
"""
CORRIDA OFICIAL de la TC3, siguiendo el notebook de apoyo (Comparacion_Gurobi_vs_CPLEX.ipynb):
para cada instancia, la relajacion y luego el modelo entero, en Gurobi y en CPLEX, con la
configuracion por defecto (solo se fija el limite de tiempo, igual en ambos).

Uso (desde la carpeta Tarea 3):
    python codigo/correr_todo.py instancias/instancia_A_corregida.json instancias/instancia_B_corregida.json
    python codigo/correr_todo.py instancias/instancia_A_corregida.json instancias/instancia_B_corregida.json --time-limit 30 --salida prueba

Genera en resultados/:
    comparacion_gurobi_cplex.txt / .csv   tabla: instancia, tipo, solver, objetivo, tiempo_s, nodos, gap
    logs/<instancia>_<solver>_{relajacion,entero}.log
    <instancia>_<solver>_rutas.json
"""
import argparse
import os

from datos import leer_instancia
from experimentos import correr_entero, correr_relajacion, filas, guardar_tabla, solvers_a_correr


def main():
    p = argparse.ArgumentParser(description='TC3: relajacion + entero en Gurobi y CPLEX')
    p.add_argument('instancias', nargs='+', help='archivos JSON de las instancias')
    p.add_argument('--time-limit', type=float, default=600, help='limite de tiempo del entero (s), igual en ambos')
    p.add_argument('--threads', type=int, default=0, help='0 = valor por defecto de cada solver')
    p.add_argument('--repeticiones', type=int, default=5,
                   help='veces que se resuelve cada LP para promediar su tiempo (por defecto 5)')
    p.add_argument('--solo', choices=['gurobi', 'cplex'], help='correr un solo solver')
    p.add_argument('--salida', default='resultados', help='carpeta de resultados')
    p.add_argument('--verbose', action='store_true', help='mostrar el log del entero en pantalla')
    args = p.parse_args()

    os.makedirs(os.path.join(args.salida, 'logs'), exist_ok=True)
    solvers = solvers_a_correr(args.solo)
    todas = []
    for archivo in args.instancias:
        d = leer_instancia(archivo)
        print(f"\n=== {d['nombre']}: n={d['n']} clientes, {d['T']} dias, {d['R']} rutas, Q={d['Q']}, "
              f"pedidos por dia={[len(d['Ct'][t]) for t in range(d['T'])]}, M={d['M']:.1f}")
        rel = correr_relajacion(d, solvers, os.path.join(args.salida, 'logs'), args.repeticiones)
        ent = correr_entero(d, solvers, args.salida, args.time_limit, args.threads, args.verbose)
        filas_ent = filas(d, 'Entero', ent)
        for fila, s in zip(filas_ent, ent):
            z_lp, z = rel[s]['obj'], ent[s]['obj']
            fila['brecha_integralidad_pct'] = 100 * (z - z_lp) / z if z and z_lp is not None else None
            print(f"[{s}] brecha de integralidad = {fila['brecha_integralidad_pct']:.2f}%"
                  + ('' if ent[s]['gap'] == 0 else ' (con el mejor entero obtenido, sin optimo probado)')
                  if fila['brecha_integralidad_pct'] is not None else f'[{s}] brecha de integralidad: -')
        todas += filas(d, 'Relajación', rel) + filas_ent
    guardar_tabla(todas, args.salida, 'comparacion_gurobi_cplex',
                  f'time_limit={args.time_limit} s, threads={"defecto" if args.threads == 0 else args.threads}, '
                  f'repeticiones por LP={args.repeticiones}')


if __name__ == '__main__':
    main()
