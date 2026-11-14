# -*- coding: utf-8 -*-
"""
Relajacion continua en Gurobi y CPLEX, y validacion cruzada entre ambos.

  Gurobi: Model.relax() sobre el modelo entero.
  CPLEX:  LinearRelaxer.make_relaxed_model(mdl) (binarias X y Z -> continuas en [0, 1]).

Ambos deben dar el mismo z_LP (salvo diferencias numericas ~1e-9).

Uso (desde la carpeta Tarea 3):
    python codigo/relajacion.py instancias/instancia_A_corregida.json instancias/instancia_B_corregida.json
    python codigo/relajacion.py instancias/instancia_B_corregida.json --solo cplex

Cada LP se resuelve 5 veces (--repeticiones) y se reporta el tiempo promedio, porque un solo
tiempo de milisegundos es ruidoso.

Guarda resultados/relajacion.txt y .csv, y los logs en resultados/logs/.
"""
import argparse
import os

from datos import leer_instancia
from experimentos import correr_relajacion, filas, guardar_tabla, solvers_a_correr


def main():
    p = argparse.ArgumentParser(description='Relajacion continua en Gurobi y CPLEX')
    p.add_argument('instancias', nargs='+', help='archivos JSON de las instancias')
    p.add_argument('--solo', choices=['gurobi', 'cplex'], help='correr un solo solver')
    p.add_argument('--salida', default='resultados', help='carpeta de resultados')
    p.add_argument('--repeticiones', type=int, default=5,
                   help='veces que se resuelve cada LP para promediar el tiempo (por defecto 5)')
    args = p.parse_args()

    os.makedirs(os.path.join(args.salida, 'logs'), exist_ok=True)
    todas = []
    for archivo in args.instancias:
        d = leer_instancia(archivo)
        print(f"\n=== {d['nombre']}: n={d['n']}, pedidos por dia={[len(d['Ct'][t]) for t in range(d['T'])]}")
        res = correr_relajacion(d, solvers_a_correr(args.solo), os.path.join(args.salida, 'logs'), args.repeticiones)
        todas += filas(d, 'Relajación', res)
    guardar_tabla(todas, args.salida, 'relajacion', f'repeticiones por LP = {args.repeticiones}')


if __name__ == '__main__':
    main()
