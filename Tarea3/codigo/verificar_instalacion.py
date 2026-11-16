# -*- coding: utf-8 -*-
"""Revisa que Gurobi y CPLEX tengan licencia completa y que las instancias existan.

Uso (desde la carpeta Tarea3):
    ..\\.venv\\Scripts\\python.exe codigo/verificar_instalacion.py
    ..\\.venv\\Scripts\\python.exe codigo/verificar_instalacion.py --arreglar-cplex

El unico problema tipico es que el paquete `cplex` de PyPI trae el motor Community
(limite de 1000 variables / 1000 restricciones). Si el CPLEX Studio instalado es el
completo, --arreglar-cplex copia su DLL sobre la del paquete pip (deja un respaldo).
"""
import argparse
import glob
import os
import platform
import re
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTANCIAS = ['instancia_A_corregida.json', 'instancia_B_corregida.json']
N_VARS_TEST = 1200      # por encima del limite 1000 de la edicion Community


def _cplex_test():
    """Resuelve un modelo de 1200 vars / 1200 restricciones. Devuelve (ok, detalle)."""
    from docplex.mp.model import Model
    try:
        m = Model(name='test_cplex')
        x = m.binary_var_list(N_VARS_TEST)
        m.minimize(m.sum(x))
        m.add_constraints(x[i] >= 1 for i in range(N_VARS_TEST))
        sol = m.solve(log_output=False)
    except Exception as e:  # DOcplexLimitsExceeded o CplexSolverError 1016
        texto = f'{type(e).__name__}: {e}'
        if '1016' in texto or 'Promotional' in texto or 'LimitsExceeded' in texto:
            return False, 'edicion Community (limite 1000 variables / 1000 restricciones)'
        return False, texto
    if sol is None or abs(sol.objective_value - N_VARS_TEST) > 1e-6:
        return False, f'solucion inesperada: {None if sol is None else sol.objective_value}'
    return True, f'{N_VARS_TEST} vars / {N_VARS_TEST} restricciones resueltas'


def _cplex_test_subproceso():
    """Corre el test en otro proceso para no reutilizar un DLL ya cargado."""
    p = subprocess.run([sys.executable, os.path.abspath(__file__), '--check-cplex'],
                       capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def _studio_dll():
    """Busca cplex2220.dll en la instalacion de CPLEX Studio."""
    candidatos = []
    for var in ('CPLEX_STUDIO_DIR222', 'CPLEX_STUDIO_DIR2212', 'CPLEX_STUDIO_DIR2211'):
        if os.environ.get(var):
            candidatos.append(os.path.join(os.environ[var], 'cplex', 'bin', 'x64_win64', 'cplex2220.dll'))
    candidatos += glob.glob(r'C:\Program Files\IBM\ILOG\CPLEX_Studio*\cplex\bin\x64_win64\cplex2220.dll')
    for c in candidatos:
        if os.path.isfile(c):
            return c
    return None


def _arreglar_cplex():
    import cplex
    destino = os.path.join(os.path.dirname(os.path.abspath(cplex.__file__)), '_internal', 'cplex2220.dll')
    origen = _studio_dll()
    if not origen:
        return False, 'no encontre el CPLEX Studio instalado (cplex2220.dll)'
    if not os.path.isfile(destino):
        return False, f'no existe el DLL del paquete pip: {destino}'
    respaldo = destino + '.community.bak'
    if not os.path.exists(respaldo):
        shutil.copy2(destino, respaldo)
    shutil.copy2(origen, destino)
    return True, f'copiado {origen} -> {destino} (respaldo: {respaldo})'


def _gurobi_licencia():
    rutas = [os.environ.get('GRB_LICENSE_FILE'), os.path.expanduser('~/gurobi.lic'),
             r'C:\gurobi.lic', os.path.join(os.environ.get('GUROBI_HOME', ''), '..', '..', 'gurobi.lic')]
    for r in rutas:
        if r and os.path.isfile(r):
            datos = {}
            with open(r, encoding='utf-8', errors='ignore') as f:
                for linea in f:
                    if '=' in linea:
                        k, v = linea.split('=', 1)
                        datos[k.strip()] = v.strip()
            return datos, r
    return {}, None


def _procesador():
    try:
        return f"{platform.processor()} | {os.cpu_count()} nucleos"
    except Exception:
        return f"{os.cpu_count()} nucleos"


def main():
    p = argparse.ArgumentParser(description='Verifica Gurobi + CPLEX y las instancias')
    p.add_argument('--arreglar-cplex', action='store_true',
                   help='copiar el motor completo del CPLEX Studio sobre el paquete pip')
    p.add_argument('--check-cplex', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args()

    if args.check_cplex:
        ok, detalle = _cplex_test()
        print(detalle)
        return 0 if ok else 2

    fallas = []
    print(f"Sistema: {platform.system()} {platform.release()} | Python {platform.python_version()} | {_procesador()}")

    # --- Gurobi ---
    try:
        import gurobipy as gp
        lic, ruta = _gurobi_licencia()
        version_lic = lic.get('VERSION')
        tipo = lic.get('TYPE', '?')
        vence = lic.get('EXPIRATION', '?')
        if version_lic and version_lic != str(gp.gurobi.version()[0]):
            raise RuntimeError(f'gurobipy {gp.gurobi.version()} no coincide con la licencia VERSION={version_lic}')
        m = gp.Model('test_gurobi')
        m.Params.OutputFlag = 0
        x = m.addVars(2500, lb=0, ub=1)
        m.setObjective(gp.quicksum(x[i] for i in range(2500)), gp.GRB.MAXIMIZE)
        m.optimize()
        if m.Status != gp.GRB.OPTIMAL:
            raise RuntimeError(f'estado {m.Status}')
        extra = f'licencia VERSION={version_lic} {tipo} (vence {vence})' if ruta else 'licencia no encontrada en disco'
        print(f"Gurobi: gurobipy {'.'.join(map(str, gp.gurobi.version()))} | {extra} | 2500 vars: OK")
    except Exception as e:
        fallas.append(f'Gurobi: {type(e).__name__}: {e}')
        print(f'Gurobi: FALLA - {type(e).__name__}: {e}')

    # --- CPLEX ---
    try:
        import cplex
        import docplex
        ok, detalle = _cplex_test_subproceso()
        if not ok and args.arreglar_cplex:
            print(f'CPLEX: {detalle}')
            print('       intentando usar el motor del CPLEX Studio...')
            arreglado, msg = _arreglar_cplex()
            print(f'       {msg}')
            if arreglado:
                ok, detalle = _cplex_test_subproceso()
        if ok:
            print(f'CPLEX: cplex {cplex.__version__} | docplex {docplex.__version__} | {detalle}: OK')
        else:
            fallas.append(f'CPLEX: {detalle}')
            print(f'CPLEX: FALLA - {detalle}')
            print('       Si tienes el CPLEX Studio completo instalado, corre:')
            print('         python codigo/verificar_instalacion.py --arreglar-cplex')
            print('       Si no, descarga la edicion academica desde IBM SkillsBuild Technology Access.')
    except Exception as e:
        fallas.append(f'CPLEX: {type(e).__name__}: {e}')
        print(f'CPLEX: FALLA - {type(e).__name__}: {e}')

    # --- Instancias ---
    faltan = [n for n in INSTANCIAS if not os.path.isfile(os.path.join(BASE, 'instancias', n))]
    if faltan:
        fallas.append(f'faltan instancias: {faltan}')
        print(f'Instancias: FALLA - faltan {faltan}')
    else:
        print(f"Instancias: {', '.join(INSTANCIAS)}: OK")

    print()
    if fallas:
        print('FALLA: revisa los mensajes de arriba.')
        return 1
    print('Todo listo para la corrida oficial')
    return 0


if __name__ == '__main__':
    sys.exit(main())
