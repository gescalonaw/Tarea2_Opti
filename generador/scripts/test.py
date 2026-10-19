import numpy as np
import generate_instances as gen
from rich import print


def validar_instancia(sub):
    """
    Imprime validaciones para cualquier instancia retornada por generar_instancia.
    """

    n = len(sub["clientes"])
    D = sub["D"]
    R = sub["R"]
    Q = sub["Q"]
    asignacion = sub["asignacion"]

    print("=" * 60)
    print(f"  n={n} clientes | D={D} dias | R={R} rutas | Q={Q}")
    print("=" * 60)

    print(f"Id's clientes: {sorted(c["id_original"] for c in sub["clientes"])}")

    # --- Validacion de demanda ---
    total = []
    print("\n[Demanda por dia y ruta]") # Esta demanda se basa en los resulados de Q_minimo que no pueden ser distintos con respecto a los del solver
    for t in range(D):
        carga = [sum(cliente["q_dia"][t] for cliente, ruta in zip(sub["clientes"], asignacion) if ruta == r) for r in range(R)]
        print(f"    Dia {t+1}: {carga}")
        total.append(sum(carga))

    print("\n[Demanda por dia]")
    for t in range(D):
        activos = sum(1 for c in sub["clientes"] if c["q_dia"][t] > 0)
        print(f"    Dia {t+1}: total={total[t]}, clientes activos={activos}")

    # --- Validacion de distancias ---
    td = sub["td"]
    N = len(td)
    print("\n[Matriz de distancias]")
    print(f"    Tamaño: {N}x{N}")
    print(f"    Diagonal nula: {all(td[i][i] == 0 for i in range(N))}")
    print(f"    Simetrica: {all(abs(td[i][j] - td[j][i]) < 1e-9 for i in range(N) for j in range(N))}")
    print(f"    td[0][n+1]={td[0][n+1]:.2f} (debe ser 0, mismo deposito)")

    # --- Validacion de cotas y Big-M ---
    for nivel, etiqueta in ((1, "ajustado"), (2, "flojo")):
        lb, ub = gen.calcular_cotas(sub, nivel)
        inalcanzables = [i for i in range(len(lb)) if lb[i] > ub[i]]

        M    = gen.calcular_M(sub, lb, ub)
        M0   = gen.calcular_M0(sub, lb)
        Mfin = gen.calcular_Mfin(sub, ub)

        M_clientes = M[1:n+1, 1:n+1]
        mascara    = ~np.eye(n, dtype=bool)

        print(f"\n[Big-M {etiqueta} (nivel={nivel})]")
        print(f"    lb: {np.round(lb, 1)}")
        print(f"    ub: {np.round(ub, 1)}")
        print(f"    Inalcanzables: {inalcanzables}")
        print(f"    M max={M.max():.1f} | M promedio={M_clientes[mascara].mean():.1f}")
        print(f"    M0: {np.round(M0, 1)}")
        print(f"    Mfin: {np.round(Mfin, 1)}")

    print()


# ---------------------------------------------------------------------------
# Instancias a probar — agrega o modifica las que necesites
# ---------------------------------------------------------------------------

instancias = [
    dict(
        ruta_txt="data/Solomon/C101.txt",
        nombre_instancia="instancia_A",
        n_clientes=15,
        id_centro=1,
        n_dias=3,
        n_rutas=3,
        probabilidad_pedido=0.8,
        probabilidad_ventana=0.6,
        holgura=0.05,
        semilla=1,
    ),
    dict(
        ruta_txt="data/Solomon/R101.txt",
        nombre_instancia="instancia_B",
        n_clientes=15,
        id_centro=93,
        n_dias=3,
        n_rutas=3,
        probabilidad_pedido=0.8,
        probabilidad_ventana=0.6,
        holgura=0.05,
        semilla=2,
    ),
]

for params in instancias:
    print(f"\n{'#'*60}")
    print(f"  Instancia: {params['nombre_instancia']}")
    print(f"{'#'*60}")
    sub = gen.generar_instancia(**params)
    validar_instancia(sub)