# -*- coding: utf-8 -*-
"""
Modelo entero en Gurobi y CPLEX con la configuracion por defecto de cada solver.
Lo unico que se fija es el limite de tiempo, igual para ambos (600 s por defecto).
Cada solucion se revisa fuera del solver (rutas, capacidad, ventanas, distancia).

Uso (desde la carpeta Tarea 3):
    python codigo/entero.py instancias/instancia_A_corregida.json instancias/instancia_B_corregida.json
    python codigo/entero.py instancias/instancia_B_corregida.json --time-limit 30

Guarda resultados/entero.txt y .csv, las rutas en JSON y los logs en resultados/logs/.
"""
import argparse
import os

from datos import leer_instancia
from experimentos import correr_entero, filas, guardar_tabla, solvers_a_correr


def main():
    p = argparse.ArgumentParser(description='Modelo entero en Gurobi y CPLEX')
    p.add_argument('instancias', nargs='+', help='archivos JSON de las instancias')
    p.add_argument('--time-limit', type=float, default=600, help='limite de tiempo por corrida (s), igual en ambos')
    p.add_argument('--threads', type=int, default=0, help='0 = valor por defecto de cada solver')
    p.add_argument('--solo', choices=['gurobi', 'cplex'], help='correr un solo solver')
    p.add_argument('--salida', default='resultados', help='carpeta de resultados')
    p.add_argument('--verbose', action='store_true', help='mostrar el log del solver en pantalla')
    args = p.parse_args()

    os.makedirs(os.path.join(args.salida, 'logs'), exist_ok=True)
    todas = []
    for archivo in args.instancias:
        d = leer_instancia(archivo)
        print(f"\n=== {d['nombre']}: n={d['n']}, pedidos por dia={[len(d['Ct'][t]) for t in range(d['T'])]}, "
              f"limite={args.time_limit:.0f} s")
        res = correr_entero(d, solvers_a_correr(args.solo), args.salida, args.time_limit, args.threads, args.verbose)
        todas += filas(d, 'Entero', res)
    guardar_tabla(todas, args.salida, 'entero',
                  f'time_limit={args.time_limit} s, threads={"defecto" if args.threads == 0 else args.threads}')


if __name__ == '__main__':
    main()
