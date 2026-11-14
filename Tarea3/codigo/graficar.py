# -*- coding: utf-8 -*-
"""
Graficos para el pitch de la TC3.

  python codigo/graficar.py instancia instancias/instancia_A_corregida.json
      -> figuras/instancia_A.png: un panel por dia; clientes con pedido en color,
         sin pedido en gris; cuadrado = cliente con ventana de tiempo; tamano = demanda.

  python codigo/graficar.py rutas instancias/instancia_A_corregida.json resultados/instancia_A_gurobi_rutas.json
      -> figuras/instancia_A_gurobi_rutas.png: las rutas de la solucion, un panel por dia,
         un color por ruta (el mismo todos los dias: consistencia).
"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

COLORES = ['#2a6fdb', '#e8590c', '#2b8a3e', '#ae3ec9', '#c92a2a']


def cargar(archivo):
    with open(archivo, encoding='utf-8') as f:
        return json.load(f)


def deposito(inst):
    if 'deposito' in inst:
        return inst['deposito']['x'], inst['deposito']['y']
    # el deposito no viene con coordenadas en el JSON: se recupera desde la
    # distancia a dos clientes (trilateracion simple con los 3 primeros)
    import numpy as np
    c = inst['clientes'][:3]
    p = np.array([[cl['x'], cl['y']] for cl in c])
    r = np.array([inst['td'][0][k + 1] for k in range(3)])
    A = 2 * (p[1:] - p[0])
    b = (r[0] ** 2 - r[1:] ** 2) + (p[1:] ** 2).sum(1) - (p[0] ** 2).sum()
    return np.linalg.solve(A, b)


def ejes(inst, ncols):
    fig, axs = plt.subplots(1, ncols, figsize=(4.6 * ncols, 4.6), sharex=True, sharey=True)
    xs = [c['x'] for c in inst['clientes']]
    ys = [c['y'] for c in inst['clientes']]
    dx, dy = deposito(inst)
    for ax in axs:
        ax.set_aspect('equal')
        ax.set_xlim(min(xs + [dx]) - 4, max(xs + [dx]) + 4)
        ax.set_ylim(min(ys + [dy]) - 4, max(ys + [dy]) + 4)
        ax.grid(alpha=0.25)
        ax.plot(dx, dy, marker='*', color='black', markersize=16, zorder=5)
    return fig, axs, (dx, dy)


def graficar_instancia(archivo, carpeta='figuras'):
    inst = cargar(archivo)
    fig, axs, _ = ejes(inst, inst['D'])
    for t, ax in enumerate(axs):
        activos = 0
        for c in inst['clientes']:
            q = c['q_dia'][t]
            pide = q > 0
            activos += pide
            ax.scatter(c['x'], c['y'], s=30 + 6 * q if pide else 30,
                       marker='s' if c.get('tiene_ventana') else 'o',
                       color=COLORES[0] if pide else '#bbbbbb', alpha=0.9 if pide else 0.6,
                       edgecolor='black' if pide else 'none', linewidth=0.6, zorder=4)
            ax.annotate(str(c['id']), (c['x'], c['y']), xytext=(4, 4), textcoords='offset points', fontsize=7)
        ax.set_title(f'Dia {t + 1}: {activos} de {inst["n"]} clientes piden')
    fig.suptitle(f'{inst["nombre"]}: n={inst["n"]}, Q={inst["Q"]}  '
                 '(estrella = deposito, cuadrado = con ventana, gris = sin pedido ese dia)', fontsize=11)
    fig.tight_layout()
    os.makedirs(carpeta, exist_ok=True)
    salida = os.path.join(carpeta, f'{inst["nombre"]}.png')
    fig.savefig(salida, dpi=160)
    print('guardado', salida)


def graficar_rutas(archivo_inst, archivo_rutas, carpeta='figuras'):
    inst, sol = cargar(archivo_inst), cargar(archivo_rutas)
    fig, axs, (dx, dy) = ejes(inst, inst['D'])
    pos = {c['id']: (c['x'], c['y']) for c in inst['clientes']}
    for t, ax in enumerate(axs):
        for c in inst['clientes']:
            if c['q_dia'][t] == 0:
                ax.scatter(c['x'], c['y'], s=25, color='#cccccc', zorder=3)
        for r, camino in enumerate(sol['rutas'][t]):
            if not camino:
                continue
            puntos = [(dx, dy)] + [pos[i] for i in camino] + [(dx, dy)]
            ax.plot([p[0] for p in puntos], [p[1] for p in puntos], '-o', color=COLORES[r % len(COLORES)],
                    markersize=5, linewidth=1.6, label=f'Ruta {r + 1}', zorder=4)
            for i in camino:
                ax.annotate(str(i), pos[i], xytext=(4, 4), textcoords='offset points', fontsize=7)
        ax.set_title(f'Dia {t + 1}')
        ax.legend(fontsize=7, loc='best')
    fig.suptitle(f'{inst["nombre"]} - solucion {sol["solver"]} (distancia total {sol["obj"]:.2f})', fontsize=11)
    fig.tight_layout()
    os.makedirs(carpeta, exist_ok=True)
    salida = os.path.join(carpeta, f'{inst["nombre"]}_{sol["solver"]}_rutas.png')
    fig.savefig(salida, dpi=160)
    print('guardado', salida)


if __name__ == '__main__':
    if sys.argv[1] == 'instancia':
        for a in sys.argv[2:]:
            graficar_instancia(a)
    elif sys.argv[1] == 'rutas':
        graficar_rutas(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
