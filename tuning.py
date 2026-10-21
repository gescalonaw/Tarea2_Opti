# -*- coding: utf-8 -*-
"""
Ajuste automatico de parametros del MIP (ConRVP-SLA) con Gurobi: Model.tune().

Que hace
    1. Resuelve el MIP con las OPCIONES MANUALES (que se pueden pasar por CLI),
       para tener una linea base reproducible.
    2. Corre Model.tune(): Gurobi prueba automaticamente distintos conjuntos de
       parametros y se queda con los que mejoran el desempeno (menor tiempo hasta
       optimalidad certificada; si el modelo no cierra dentro del limite, el
       criterio secundario es el gap/objetivo/cota, segun la instancia).
    3. Reporta el caso base y TODOS los conjuntos que devolvio el tuner, marca
       claramente el mejor, y verifica lo que promete:
         - resuelve con el mejor conjunto y compara contra el caso base;
         - resuelve con las OPCIONES MANUALES y compara;
         - vuelve a resolver con el mejor conjunto y compara los dos resultados
           entre si, como chequeo de reproducibilidad.

Recordatorio de la API (gurobipy 13)
    - Model.tune() no recibe argumentos.
    - Model.TuneResultCount y Model.getTuneResult(i).
    - El resultado 0 es SIEMPRE el caso base; el 1 es el mejor hallado. Por eso
      se pide TuneResults >= 2 (por defecto -1 = frontera eficiente).
    - No existe Model.TuneStatus en gurobipy 13. Si el tuner se corta por tiempo
      o se interrumpe, lo unico observable es TuneResultCount; el script lo
      advierte explicitamente cuando no hay ningun resultado.
    - writeTuneResult(i, archivo) guarda el detalle del conjunto i en un archivo
      (util para evidencia; NO se usa por defecto para no ensuciar resultados/).

Uso (desde la raiz del repo):
    python tuning.py
    python tuning.py generador/data/instancias/instancia_A.json
    python tuning.py generador/data/instancias/instancia_B.json --tiempo-tune 300
    python tuning.py generador/data/instancias/instancia_A.json --limite-solve 120 --trials 2 --seed 7
    python tuning.py --no-verificar            # corre el tuner y muestra resultados
    python tuning.py --opciones "MIPFocus=1;Heuristics=0.3"   # caso base manual

Salida: pantalla y resultados/tuning_<nombre_instancia>.txt
"""

import argparse
import os

from gurobipy import GRB

from modelo import leer_instancia, armar_modelo


# ---------------------------------------------------------------------------
# Configuracion editable: opciones manuales que se usan como caso base y con las
# que se compara el resultado del tuner. Tambien se pueden pasar por --opciones.
# ---------------------------------------------------------------------------
OPCIONES_MANUALES = {
    "MIPFocus": 1,
    "Heuristics": 0.2,
    "Cuts": 2,
}

# Parametros que NO son del MIP/PL y que no tiene sentido comparar (licencia,
# servidores, multiobjetivo, rutas de archivos, etc.). Las claves que empiecen
# con "Tune" tambien se excluyen porque son del propio tuner.
PREFIJOS_IGNORADOS = ("CS", "WLSAccess", "WLSSecret", "WLSToken", "WLS")
NOMBRES_IGNORADOS = {"ComputeServer", "ServerPassword", "TokenServer", "WorkerPool",
                     "ResultFile", "InputFile", "LogFile", "NodefileDir",
                     "MultiObjSettings", "ConcurrentSettings",
                     "Username", "LicenseID", "LicenseFile", "CloudAccessID",
                     "CloudSecretKey", "CloudPool"}


def es_comparable(nombre):
    """True si el parametro es del MIP/PL y no de infraestructura del tuner."""
    if nombre.startswith("Tune"):
        return False
    if nombre.startswith(PREFIJOS_IGNORADOS):
        return False
    return nombre not in NOMBRES_IGNORADOS


def leer_texto_parametro(modelo, nombre):
    """Valor actual de un parametro como texto legible."""
    try:
        valor = getattr(modelo.Params, nombre)
        if isinstance(valor, float):
            return f"{valor:g}"
        return str(valor)
    except Exception:
        return "?"


def parametros_del_tuner(modelo, nombres):
    """{parametro: valor real} de los parametros del MIP/PL cuyo valor actual
    difiere del default. Se usa para re-aplicar el set del tuner y para el reporte.
    """
    cambios = {}
    for nombre in nombres:
        try:
            info = modelo.getParamInfo(nombre)
        except Exception:
            continue
        valor, default = info[2], info[5]
        if valor != default:
            cambios[nombre] = valor
    return cambios


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def leer_cli():
    p = argparse.ArgumentParser(
        description="Ajuste automatico de parametros del MIP con Model.tune().")
    p.add_argument("instancia", nargs="?", default="generador/data/instancias/instancia_A.json",
                   help="ruta del JSON de la instancia")
    p.add_argument("--limite-solve", type=float, default=600,
                   help="TimeLimit (s) para el caso base y para verificar el mejor set (default 600)")
    p.add_argument("--tiempo-tune", type=float, default=300,
                   help="TuneTimeLimit (s) del tuner (default 300)")
    p.add_argument("--trials", type=int, default=0,
                   help="TuneTrials: repeticiones por set con distinta Seed (0 = automatico)")
    p.add_argument("--results", type=int, default=-1,
                   help="TuneResults: cuantos sets retener (-1 = frontera eficiente)")
    p.add_argument("--seed", type=int, default=0,
                   help="Seed del modelo para reproducibilidad (0 = default de Gurobi)")
    p.add_argument("--criterio", type=int, default=-1, choices=[-1, 0, 1, 2, 3],
                   help="TuneCriterion: -1 auto, 0 tiempo, 1 gap, 2 objetivo, 3 cota")
    p.add_argument("--threads", type=int, default=1,
                   help="Threads para el caso base y la verificacion (default 1)")
    p.add_argument("--hilos-tune", type=int, default=0,
                   help="Threads durante el tune (default 0 = todos los nucleos)")
    p.add_argument("--opciones", type=str, default=None,
                   help='caso base manual, formato "Param=valor;Param2=valor2"')
    p.add_argument("--salida-tuner", action="store_true",
                   help="guardar tambien el detalle del tuner en resultados/tuning_detalle_<instancia>.txt")
    p.add_argument("--no-verificar", action="store_true",
                   help="no re-resolver el modelo con el mejor set ni con las opciones manuales")
    return p.parse_args()


def parsear_opciones(texto):
    """'MIPFocus=1;Heuristics=0.3' -> {'MIPFocus': 1, 'Heuristics': 0.3}"""
    opciones = {}
    for trozo in texto.split(";"):
        trozo = trozo.strip()
        if not trozo:
            continue
        if "=" not in trozo:
            raise SystemExit(f"Opcion mal escrita: '{trozo}' (usa Param=valor)")
        nombre, valor = (x.strip() for x in trozo.split("=", 1))
        try:
            valor = int(valor) if valor.lstrip("-").isdigit() else float(valor)
        except ValueError:
            pass
        opciones[nombre] = valor
    return opciones


# ---------------------------------------------------------------------------
# Resolver con un conjunto de parametros y devolver una metrica comparable.
# ---------------------------------------------------------------------------
def resolver_con(d, parametros):
    parametros = dict(parametros or {})
    limite = parametros.pop("TimeLimit", None)
    m, *_ = armar_modelo(d)
    m.Params.OutputFlag = 0
    for nombre, valor in parametros.items():
        setattr(m.Params, nombre, valor)
    if limite is not None:
        m.Params.TimeLimit = limite
    m.optimize()
    return m


def resumir(m):
    """Metricas de una corrida, sin resolver de nuevo."""
    if m.SolCount == 0:
        return {"estado": "SIN SOLUCION", "objetivo": None, "cota": m.ObjBound,
                "gap": None, "tiempo": m.Runtime, "nodos": m.NodeCount, "optimo": False}
    return {
        "estado": "OPTIMAL" if m.Status == GRB.OPTIMAL else "TIME_LIMIT",
        "objetivo": m.ObjVal,
        "cota": m.ObjBound,
        "gap": 100 * m.MIPGap,
        "tiempo": m.Runtime,
        "nodos": m.NodeCount,
        "optimo": m.Status == GRB.OPTIMAL,
    }


def val(r, dec=1, sufijo=""):
    return "-" if r is None else f"{r:.{dec}f}{sufijo}"


def texto_mejora(base, nuevo, dec=2):
    """Mejora porcentual de `nuevo` respecto de `base` (menor es mejor)."""
    if base is None or nuevo is None or base == 0:
        return "-"
    return f"{100 * (nuevo - base) / base:+.{dec}f} %"


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------
def main():
    args = leer_cli()
    opciones = dict(OPCIONES_MANUALES, TimeLimit=args.limite_solve)
    if args.seed:
        opciones["Seed"] = args.seed
    if args.opciones:
        opciones = {**parsear_opciones(args.opciones), "TimeLimit": args.limite_solve}
        if args.seed:
            opciones["Seed"] = args.seed

    d = leer_instancia(args.instancia)
    lineas = []

    def emitir(linea=""):
        print(linea)
        lineas.append(linea)

    # Referencia de nombres de parametros: los del modelo real (207 atributos).
    m0, *_ = armar_modelo(d)
    todos = [p for p in dir(m0.Params) if not p.startswith("_") and es_comparable(p)]

    emitir(f"Instancia: {d['nombre']} | clientes = {d['n']} | dias = {d['T']} | "
           f"rutas = {d['R']} | Q = {d['Q']}")
    emitir(f"Presupuesto: limite por solve = {args.limite_solve:.0f} s | "
           f"tiempo de tune = {args.tiempo_tune:.0f} s | threads solve = {args.threads} | "
           f"threads tune = {args.hilos_tune or 'todos'}")
    emitir("")

    # ---------------- 1. Caso base: parametros manuales ----------------
    emitir("=" * 72)
    emitir("1. CASO BASE (opciones manuales)")
    emitir("=" * 72)
    parametros_base = {**opciones, "Threads": args.threads}
    emitir(f"Parametros: {', '.join(f'{k}={v}' for k, v in sorted(parametros_base.items()))}")
    m_base = resolver_con(d, parametros_base)
    base = resumir(m_base)
    emitir(f"Distancia = {val(base['objetivo'])} | cota = {val(base['cota'])} | "
           f"gap = {val(base['gap'], 2, ' %')} | tiempo = {val(base['tiempo'])} s | "
           f"nodos = {base['nodos']} | estado = {base['estado']}")
    emitir("")

    # ---------------- 2. Model.tune() ----------------
    emitir("=" * 72)
    emitir("2. Model.tune()")
    emitir("=" * 72)
    m, *_ = armar_modelo(d)
    for nombre, valor in opciones.items():
        setattr(m.Params, nombre, valor)
    m.Params.Threads = args.hilos_tune
    m.Params.TuneTimeLimit = args.tiempo_tune
    if args.results >= 2:
        m.Params.TuneResults = args.results
    if args.trials:
        m.Params.TuneTrials = args.trials
    if args.criterio != -1:
        m.Params.TuneCriterion = args.criterio
    m.Params.TuneOutput = 2   # resumen de cada conjunto que se prueba

    emitir(f"TuneTimeLimit = {args.tiempo_tune:.0f} s | TuneResults = "
           f"{m.Params.TuneResults:.0f} | TuneTrials = {m.Params.TuneTrials:.0f} | "
           f"TuneCriterion = {m.Params.TuneCriterion:.0f} | TuneMetric = {m.Params.TuneMetric:.0f}")
    emitir("(el tuner decide solo que parametros probar; TuneResults >= 2 para obtener el mejor)")
    emitir("")
    m.tune()

    n = m.TuneResultCount
    emitir(f"TuneResultCount = {n}")
    if n == 0:
        emitir("ADVERTENCIA: el tuner no devolvio resultados (se corto por TuneTimeLimit o se")
        emitir("interrumpio). En gurobipy 13 no hay Model.TuneStatus para distinguirlo.")
        ocupado = base["tiempo"] or 0
        emitir(f"Pista: el caso base tardo {ocupado:.1f} s; el tuner necesita varios solves completos")
        emitir(f"antes de devolver un conjunto. Con TuneTimeLimit = {args.tiempo_tune:.0f} s quizas no")
        emitir("alcance: sube --tiempo-tune (p. ej. 600-1200) o baja --limite-solve para una prueba rapida.")
        emitir("")
    elif n == 1:
        emitir("NOTA: solo vino el caso base; puede que el tuner no haya encontrado mejoras.")
        emitir("")

    # ---------------- 3. Resultados del tuner ----------------
    emitir("=" * 72)
    emitir("3. Conjuntos de parametros devueltos por el tuner")
    emitir("=" * 72)

    conjuntos = []   # (indice, es_base, cambios_reales)
    for i in range(n):
        es_base = (i == 0)
        m.getTuneResult(i)
        cambios = parametros_del_tuner(m, todos)
        conjuntos.append((i, es_base, cambios))
        etiqueta = "CASO BASE del tuner" if es_base else f"conjunto {i}"
        emitir(f"{etiqueta}: " + (", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                                            for k, v in sorted(cambios.items()))
                                  if cambios else "(sin cambios)"))
    if n == 0:
        emitir("(no hay conjuntos que listar: el tuner no alcanzo a cerrar ninguno.)")
        emitir("Para obtener resultados, dale mas presupuesto al tuner, p. ej.:")
        emitir(f"    python tuning.py {args.instancia} --tiempo-tune {max(600, int(6 * args.tiempo_tune))}")
        emitir("o reduce el costo de cada solve con un --limite-solve menor (prueba rapida).")
    emitir("")

    # comparar cada conjunto contra el caso base del tuner
    base_tuner = conjuntos[0][2] if conjuntos else {}
    if conjuntos:
        emitir("Diferencias contra el caso base del tuner:")
        for i, es_base, cambios in conjuntos:
            if es_base:
                continue
            todos_nombres = sorted(set(cambios) | set(base_tuner))
            difs = {k: (base_tuner.get(k), cambios.get(k)) for k in todos_nombres
                    if base_tuner.get(k) != cambios.get(k)}
            emitir(f"  conjunto {i}: " + (", ".join(f"{k}: {a} -> {b}" for k, (a, b) in difs.items())
                                         if difs else "(sin diferencias con el caso base)"))
        emitir("")

    if args.salida_tuner and n:
        os.makedirs("resultados", exist_ok=True)
        detalle = os.path.join("resultados", f"tuning_detalle_{d['nombre']}.txt")
        try:
            m.writeTuneResult(1 if n > 1 else 0, detalle)
            emitir(f"Detalle del mejor conjunto guardado en {detalle}")
        except Exception as e:
            emitir(f"No se pudo guardar el detalle del tuner: {type(e).__name__}: {e}")
        emitir("")

    # ---------------- 4. Verificacion: mejor set vs manuales vs reproducibilidad ----------------
    if args.no_verificar or n == 0:
        if n and args.no_verificar:
            emitir("(--no-verificar: no se re-resuelve con el mejor conjunto.)")
    else:
        emitir("=" * 72)
        emitir("4. Verificacion del mejor conjunto sobre la instancia")
        emitir("=" * 72)

        mejor = 1 if n > 1 else 0
        m.getTuneResult(mejor)
        cambios_mejor = parametros_del_tuner(m, todos)

        # 4a. resolver con el mejor conjunto, con el mismo TimeLimit/Threads/Seed
        conj_mejor = {**cambios_mejor, "TimeLimit": args.limite_solve, "Threads": args.threads}
        if args.seed:
            conj_mejor["Seed"] = args.seed
        m_mejor = resolver_con(d, conj_mejor)
        res_mejor = resumir(m_mejor)

        # 4b. reproducibilidad: segunda corrida con el mismo conjunto
        m_mejor2 = resolver_con(d, conj_mejor)
        res_mejor2 = resumir(m_mejor2)

        emitir(f"{'corrida':26s} {'distancia':>10s} {'cota':>10s} {'gap':>8s} "
               f"{'tiempo':>8s} {'nodos':>10s} {'optimo':>7s}")
        filas = [
            ("manuales (caso base)", base),
            ("mejor conjunto (tune)", res_mejor),
            ("mejor conjunto (2a vez)", res_mejor2),
        ]
        for nombre, r in filas:
            emitir(f"{nombre:26s} {val(r['objetivo']):>10s} {val(r['cota']):>10s} "
                   f"{val(r['gap'], 2, ' %'):>8s} {val(r['tiempo']):>8s} "
                   f"{str(r['nodos']):>10s} {str(r['optimo']):>7s}")
        emitir("")
        emitir(f"Mejora del mejor conjunto en 'distancia' respecto de las manuales: "
               f"{texto_mejora(base['objetivo'], res_mejor['objetivo'])}")
        emitir(f"Reproducibilidad (misma corrida, mismo Seed = {args.seed or 'default'}): "
               f"distancia {'igual' if res_mejor['objetivo'] == res_mejor2['objetivo'] else 'DISTINTA'}, "
               f"tiempo {val(res_mejor['tiempo'])} s vs {val(res_mejor2['tiempo'])} s")
        emitir("")

        # 4c. listado final de parametros a usar
        emitir("Conjunto de parametros recomendado (listo para pegar en resolver.py):")
        emitir("  " + ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                                for k, v in sorted(conj_mejor.items())))
        emitir("")
        if n <= 1:
            emitir("Interpretacion: el tuner NO encontro mejoras sobre las opciones manuales")
            emitir("(solo devolvio el caso base). Tu configuracion actual ya es la recomendada;")
            emitir("no hay una mejora medible que atribuir al tune en este presupuesto.")
        elif res_mejor["optimo"] and base["optimo"]:
            emitir("Interpretacion: ambas configuraciones cierran el gap. Compara 'tiempo':")
            emitir("si el mejor conjunto tarda menos, esa es la mejora del tune.")
        elif not res_mejor["optimo"]:
            emitir("Interpretacion: el modelo no cierra dentro del limite. Compara 'distancia' y 'cota':")
            emitir("una cota mas alta a igual presupuesto indica mejor desempeno del conjunto elegido.")

    # ---------------- Guardado ----------------
    os.makedirs("resultados", exist_ok=True)
    salida = os.path.join("resultados", f"tuning_{d['nombre']}.txt")
    with open(salida, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    print(f"\nResultados guardados en {salida}")


if __name__ == "__main__":
    main()
