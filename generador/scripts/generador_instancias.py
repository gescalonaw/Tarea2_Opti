# Column definitions:
    # CUST NO.     (id): Identificador del cliente (0 = depositoo)
    # XCOORD.      (x) : Coordenada X
    # YCOORD.      (y) : Coordenada Y
    # DEMAND       (q) : Cantidad demandada
    # READY TIME   (a) : Inicio de la ventana de tiempo
    # DUE DATE     (b) : Final  de la ventana de tiempo
    # SERVICE TIME (st): Duracion de la atencion al cliente
    # q_dia            : Lista de la cantidad requerida por dia
    # tiene_ventana    : Valor booleano indicando la presencia o ausencia de una ventana de tiempo
    #capacidad      (Q): Capacidad de carga del vehiculo

import math
import random
import json
import os

import gurobipy as gp
import numpy as np

from gurobipy import GRB

def leer_txt(ruta):
    """
    Lee un archivo de texto en formato Solomon y extrae los datos de la instancia.

    Parsea el archivo linea por linea ignora los encabezados de texto. Detecta
    automaticamente la linea de dos columnas que contiene la capacidad del vehiculo,
    y las filas de siete columnas que corresponden al deposito y a cada cliente.

    Parametros:
    ruta : str
        Ruta al archivo .txt con el formato Solomon ("data/Solomon/C101.txt").

    Retorna:
    dict con las claves:
        - "capacidad" (int)  : Capacidad maxima del vehiculo segun el dataset.
        - "deposito"  (dict) : Coordenadas y ventana de tiempo del deposito
                               {"x", "y", "a", "b"}.
        - "clientes"  (list) : Lista de diccionarios, uno por nodo (incluido el
                               deposito en posicion 0), con claves
                               {"id", "x", "y", "q", "a", "b", "st"}.
    """
    capacidad = None
    filas = []

    with open(ruta) as r:
        for linea in r:
            partes = linea.split()

            # Empty or text lineas are omitted
            if len(partes) == 0:
                continue
            try:
                numeros = [float(p) for p in partes]
            except ValueError:
                continue

            # linea before header with fleet and capacidad
            if len(numeros) == 2:
                capacidad = int(numeros[1])
            # linea with the entire fila
            elif len(numeros) == 7:
                filas.append(numeros)

    # fila 0 corresponds to the deposito
    d = filas[0]
    deposito = {"x": d[1], "y": d[2], "a": d[4], "b": d[5]}

    # The remaining filas are the clientes
    clientes = []
    for fila in filas:
        clientes.append({
            "id": int(fila[0]),
            "x":      fila[1],
            "y":      fila[2],
            "q":      fila[3],
            "a":      fila[4],
            "b":      fila[5],
            "st":     fila[6]
        })

    return {
        "capacidad": capacidad,
        "deposito": deposito,
        "clientes": clientes
    }

def elegir_subconjunto(data, n, id_centro):
    """
    Selecciona un subconjunto de n clientes del dataset original agrupados
    geograficamente alrededor de un cliente de referencia.

    Toma el cliente con id igual a id_centro como punto central y ordena todos
    los clientes por distancia euclidiana a ese punto, seleccionando los n mas
    cercanos. Luego renumera sus identificadores del 1 al n para garantizar
    consistencia en los indices del modelo.

    Parametros:
    data : dict
        Diccionario retornado por leer_txt con claves "deposito" y "clientes".
    n : int
        Cantidad de clientes a seleccionar.
    id_centro : int
        Identificador del cliente que se usa como centro geografico de referencia.

    Retorna:
    dict con las claves:
        - "deposito" (dict) : Datos del deposito sin modificar.
        - "clientes" (list) : Lista de n clientes mas cercanos al centro,
                              con un campo "id_original" que preserva el id
                              del dataset y un nuevo campo "id" renumerado.
    """
    deposito = data["deposito"]
    clientes = data["clientes"]

    # A customer we use as a reference in the area
    center = next((c for c in clientes if c["id"] == id_centro), None)

    if center is None:
        raise ValueError(f"There is no customer with ID: {id_centro}")

    # Calculo de distancia euclidiana, ordenamiento de menor a mayor y seleccion de los primeros n
    chosen = sorted(
        clientes,
        key=lambda c: math.hypot(c["x"] - center["x"], c["y"] - center["y"])
    )[:n]

    # Renumeracion para consistencia de los id's
    for new_id , c in enumerate(chosen, start=1):
        c["id_original"] = c["id"]
        c["id"] = new_id

    return {"deposito": deposito, "clientes": chosen}

def generar_pedidos(sub, dias, probabilidad_pedido, semilla):
    """
    Genera la demanda diaria de cada cliente de forma estocastica.

    Para cada cliente y cada dia, lanza una variable aleatoria con la
    probabilidad dada. Si el cliente realiza un pedido ese dia, su demanda
    se calcula como la demanda base del dataset multiplicada por un factor
    de variacion uniforme en [0.7, 1.3]. Si no realiza pedido, su demanda
    es 0. Se garantiza que todo cliente realiza al menos un pedido durante
    el horizonte de planificacion.

    El resultado se almacena en el campo "q_dia" de cada cliente: una lista
    de longitud [dias] donde q_dia[t] es la demanda del cliente en el dia t+1.

    Parametros:
    sub : dict
        Diccionario con clave "clientes" (lista de clientes con campo "q").
    dias : int
        Numero de dias del horizonte de planificacion.
    probabilidad_pedido : float
        Probabilidad de que un cliente realice un pedido en un dia dado.
    semilla : int
        Semilla para el generador de numeros aleatorios, garantiza reproducibilidad.

    Retorna:
    dict
        El mismo diccionario sub con el campo "q_dia" agregado a cada cliente.
    """

    rng = random.Random(semilla)

    for c in sub["clientes"]:
        q_base = c["q"]
        q_dia = []

        for t in range(dias):
            if rng.random() < probabilidad_pedido:
                # Factor de variacion de la demanda del cliente dada por el dataset
                u = rng.uniform(0.7, 1.3)
                q_dia.append(max(1, round(q_base * u)))
            else:
                q_dia.append(0)

        # Todos los clientes piden al menos en un dia
        if sum(q_dia) == 0:
            force_day = rng.randrange(dias)
            q_dia[force_day] = max(1, round(q_base))

        c["q_dia"] = q_dia

    return sub

def asignar_ventanas(sub, probabilidad_ventana, semilla):
    """
    Determina de forma aleatoria que clientes tienen restriccion de ventana de tiempo activa.

    Las ventanas de tiempo (campos "a" y "b") ya vienen definidas en el dataset de Solomon
    para todos los clientes. Esta funcion agrega el campo booleano "tiene_ventana" a cada
    cliente: si es True, el modelo debera respetar los limites [a, b] de ese cliente;
    si es False, los valores de "a" y "b" se ignoran durante la optimizacion.

    Parametros:
    sub : dict
        Diccionario con clave "clientes" (lista de clientes con campos "a" y "b").
    probabilidad_ventana : float
        Probabilidad de que un cliente tenga ventana de tiempo activa.
    semilla : int
        Semilla para el generador de numeros aleatorios, garantiza reproducibilidad.

    Retorna:
    dict
        El mismo diccionario sub con el campo "tiene_ventana" (bool) agregado a cada cliente.
    """

    rng = random.Random(semilla)
    for c in sub["clientes"]:
        c["tiene_ventana"] = rng.random() < probabilidad_ventana
    return sub

def Q_minimo(sub, R):
    """
    Resuelve un sub-problema de optimizacion para encontrar la capacidad minima
    de vehiculo que hace factible la asignacion de clientes a rutas.

    Formula y resuelve un modelo de programacion entera (MIP) con Gurobi que
    asigna cada cliente a exactamente una ruta (variable binaria Z_i^r) y minimiza
    la capacidad Q del vehiculo, sujeto a que la carga total asignada a cada ruta
    en cualquier dia no supere Q. Al resolver este sub-problema con menos
    restricciones que el modelo principal, se obtiene una cota inferior para la
    capacidad del vehiculo. Esta cota se usa en generar_instancia para fijar Q
    con una holgura adicional, asegurando que el problema principal sea factible.

    Parametros:
    sub : dict
        Diccionario con clave "clientes", donde cada cliente tiene el campo "q_dia".
    R : int
        Numero de rutas (vehiculos) disponibles.

    Retorna:
    tuple (Q_min, asignacion):
        - Q_min (int)       : Capacidad minima optima del vehiculo.
        - asignacion (list) : Lista de longitud n donde asignacion[i] indica
                              a que ruta fue asignado el cliente i en la solucion optima.
    """

    # --- Datos ---
    clientes = sub["clientes"]           # Diccionario de clientes
    n         = len(clientes)             # Numero de clientes
    D         = len(clientes[0]["q_dia"]) # Numero de dias

    I     = range(n) # Indices de clientes
    rutas = range(R) # Indice de rutas
    dias  = range(D) # Indice de dias

    # Demanda del cliente i el dia t q_it
    q = [c["q_dia"] for c in clientes]

    # --- Modelo y variables ---
    m = gp.Model("Capacidad Minima") # Creacion del modelo
    m.Params.OutputFlag = 0          # Supresion de logs en consola

    z = m.addVars(I, rutas, vtype=GRB.BINARY, name="Z") # Variable de asignacion cliente ruta Z_i^r
    Q = m.addVar(vtype=GRB.INTEGER, lb=0, name="Q")    # Variable de capacidad

    # --- Restricciones ---
    m.addConstrs((gp.quicksum(z[i,r] for r in rutas) == 1 for i in I), name="asignacion")                        # Asignacion cliente ruta (2)
    m.addConstrs((gp.quicksum(q[i][t] * z[i,r] for i in I) <= Q for r in rutas for t in dias), name="capacidad") # Limite de capacidad (14)

    m.update()
    print(f"Variables totales: {m.NumVars}")
    print(f"Variables binarias: {m.NumBinVars}")
    print(f"Variables enteras: {m.NumVars - m.NumBinVars}")
    print(f"Numero de restricciones: {m.NumConstrs}")

    # --- Objetivo ---
    m.setObjective(Q, GRB.MINIMIZE)
    m.Params.TimeLimit = 60
    m.optimize()

    # --- Verificaciones ---

    # Verficacion de optimo
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Capacidad minima no optima, status = {m.Status}")

    # Impresion de capacidad real por dia y ruta
    capacidad = [[sum(q[i][t] for i in I if z[i,r].X > 0.5) for r in rutas] for t in dias]
    print(f"Capacidad por dia y ruta: {capacidad}")

    assign = [next(r for r in rutas if z[i,r].X > 0.5) for i in I]

    return int(round(Q.X)), assign

def calcular_distancias(sub):
    """
    Construye las matrices de distancia y tiempo de viaje entre todos los nodos de la instancia.

    Genera dos matrices cuadradas de tamaño (n+2) x (n+2), donde los indices
    representan: nodo 0 = deposito de salida, nodos 1..n = clientes, nodo n+1 =
    deposito de llegada (mismo punto fisico que el nodo 0, duplicado para modelar
    correctamente las rutas con retorno). Las distancias se calculan como la
    distancia euclidiana entre las coordenadas (x, y) de cada par de nodos.

    Dado que el dataset de Solomon asume velocidad unitaria (v=1), el tiempo de
    viaje tt_ij es numericamente igual a la distancia td_ij. Se generan dos
    matrices separadas para mantener consistencia con la notacion del modelo
    de optimizacion.

    Parametros:
    sub : dict
        Diccionario con claves "deposito" (con campos "x", "y") y "clientes"
        (lista de clientes con campos "x", "y").

    Retorna:
    dict
        El mismo diccionario sub con los campos agregados:
        - "td" (np.ndarray) : Matriz (n+2)x(n+2) de distancias euclidiana.
        - "tt" (np.ndarray) : Matriz (n+2)x(n+2) de tiempos de viaje (copia de td).
    """
    deposito = sub["deposito"]

    # Almacenamiento de nodos
    puntos  = [(deposito["x"], deposito["y"])]
    puntos += [(c["x"], c["y"]) for c in sub["clientes"]]
    puntos += [(deposito["x"], deposito["y"])]

    N = len(puntos)

    # Calculo de distania ecuclidiana
    td = np.zeros((N,N))
    for i in range(N):
        for j in range(N):
            td[i][j] = math.hypot(puntos[i][0] - puntos[j][0], puntos[i][1] - puntos[j][1])

    # Copia redundante
    sub["td"] = td
    sub["tt"] = td.copy()

    return sub

def calcular_cotas(sub, nivel):
    """
    Calcula las cotas inferior (lb) y superior (ub) del tiempo de inicio de
    atencion W_it para cada nodo del modelo.

    Estas cotas son fundamentales para construir un Big-M ajustado, lo que
    resulta en formulaciones MIP mas compactas y eficientes que las que usan
    la ventana del deposito como cota por defecto.

    Se calculan dos tipos de cotas segun el parametro [nivel]:
    - nivel = 1 (ajustado): Las cotas consideran el tiempo de viaje desde/hasta
      el deposito y, si el cliente tiene ventana activa ("tiene_ventana" = True),
      se intersectan con su ventana de tiempo [a, b] del dataset. Esto produce
      cotas mas estrechas y Big-M mas pequenos.
    - Cualquier otro valor (flojo): Las cotas son simplemente la ventana del
      deposito [aW, bW] para todos los nodos. Produce Big-M mas grandes y conservadores.

    Los vectores retornados tienen longitud n+2, indexados como:
        indice 0   -> deposito de salida (nodo 0)
        indices 1..n -> clientes
        indice n+1 -> deposito de llegada (nodo n+1)

    Parametros:
    sub : dict
        Diccionario con claves "deposito", "clientes" y "tt".
    nivel : int o bool
        Si es 1 o True, calcula cotas ajustadas. Cualquier otro valor usa la
        ventana del deposito como cota para todos los nodos.

    Retorna:
    tuple (lb, ub):
        - lb (np.ndarray) : Vector de cotas inferiores de longitud n+2.
        - ub (np.ndarray) : Vector de cotas superiores de longitud n+2.
    """
    deposito = sub["deposito"]
    aW, bW = deposito["a"], deposito["b"]
    clientes = sub["clientes"]
    n = len(clientes)
    tt = sub["tt"]

    # Se almacena una entrada por nodo incluyendo: nodo 0, clientes 1,...,n y nodo n+1
    lb = np.full(n + 2, float(aW))
    ub = np.full(n + 2, float(bW))

    if nivel == 1 or nivel == True:
        for i, cliente in enumerate(clientes, start=1):
            lb[i] = aW + tt[0][i]
            ub[i] = bW - cliente["st"] - tt[i][n+1]
            if cliente["tiene_ventana"]:
                lb[i] = max(lb[i], cliente["a"])
                ub[i] = min(ub[i], cliente["b"])

    return lb, ub

def calcular_M(sub, lb, ub):
    """
    Calcula la matriz Big-M para las restricciones de precedencia temporal entre clientes.

    Para cada par de clientes (i, j) con i != j, el valor M[i][j] es la cota
    superior de la expresion (W_i + st_i + tt_ij - W_j), que aparece en las
    restricciones de eliminacion de sub-tours del modelo. Un M[i][j] ajustado
    permite que el solver descarte mas rapidamente combinaciones inviables.

    La formula aplicada es:
        M[i][j] = max(0, ub[i] + st_i + tt[i][j] - lb[j])

    Los valores fuera de la diagonal para nodos de deposito (indice 0 y n+1)
    se mantienen en 0 ya que no son necesarios en el modelo.

    Parametros:
    sub : dict
        Diccionario con claves "clientes" y "tt".
    lb : np.ndarray
        Vector de cotas inferiores de longitud n+2 (retornado por calcular_cotas).
    ub : np.ndarray
        Vector de cotas superiores de longitud n+2 (retornado por calcular_cotas).

    Retorna:
    np.ndarray
        Matriz (n+2)x(n+2) con los valores Big-M para cada arco (i, j) entre clientes.
    """
    clientes = sub["clientes"]
    n = len(clientes)
    N = n + 2
    tt = sub["tt"]

    # Tiempos de atencion al cliente
    st = np.zeros(N)
    for i, cliente in enumerate(clientes, start=1):
        st[i] = cliente["st"]
    
    # Calculo de M
    M = np.zeros((N,N))
    for i in range(1, n+1):
        for j in range(1, n+1):
            if i != j:
                M[i][j] = max(0.0, ub[i] + st[i] + tt[i][j] - lb[j])

    return M

def calcular_M0(sub, lb):
    """
    Calcula el vector Big-M para las restricciones de salida desde el deposito.

    Para cada cliente j, M0[j] es la cota superior de la expresion
    (aW + tt[0][j] - W_j), que aparece en las restricciones que vinculan
    el tiempo de apertura del deposito con el tiempo de llegada al primer
    cliente de cada ruta.

    La formula aplicada es:
        M0[j] = max(0, aW + tt[0][j] - lb[j])

    Parametros:
    sub : dict
        Diccionario con claves "deposito" (campo "a") y "tt".
    lb : np.ndarray
        Vector de cotas inferiores de longitud n+2 (retornado por calcular_cotas).

    Retorna:
    np.ndarray
        Vector de longitud n+2 con los valores Big-M para los arcos desde el deposito.
        Solo los indices 1..n tienen valores significativos; el resto es 0.
    """
    aW = sub["deposito"]["a"]
    n = len(sub["clientes"])
    tt = sub["tt"]

    M0 = np.zeros(n + 2)
    for j in range(1, n+1):
        M0[j] = max(0.0, aW + tt[0][j] - lb[j])

    return M0

def calcular_Mfin(sub, ub):
    """
    Calcula el vector Big-M para las restricciones de retorno al deposito.

    Para cada cliente i, Mfin[i] es la cota superior de la expresion
    (W_i + st_i + tt[i][n+1] - bW), que aparece en las restricciones que
    garantizan que cada vehiculo regresa al deposito antes del cierre de
    su ventana de tiempo.

    La formula aplicada es:
        Mfin[i] = max(0, ub[i] + st_i + tt[i][n+1] - bW)

    Parametros:
    sub : dict
        Diccionario con claves "deposito" (campo "b"), "clientes" y "tt".
    ub : np.ndarray
        Vector de cotas superiores de longitud n+2 (retornado por calcular_cotas).

    Retorna:
    np.ndarray
        Vector de longitud n+2 con los valores Big-M para los arcos de retorno
        al deposito. Solo los indices 1..n tienen valores significativos; el resto es 0.
    """
    bW = sub["deposito"]["b"]
    n = len(sub["clientes"])
    tt = sub["tt"]

    Mfin = np.zeros(n + 2)
    for i, cliente in enumerate(sub["clientes"], start=1):
        Mfin[i] = max(0.0, ub[i] + cliente["st"] + tt[i][n + 1] - bW)

    return Mfin

def guardar(sub, nombre, carpeta):
    """
    Serializa la instancia completa en un archivo JSON dentro de la carpeta indicada.

    Calcula las cotas y valores Big-M en sus versiones ajustada y floja, y los
    incluye en el archivo de salida junto con todos los datos de la instancia:
    parametros globales, datos de clientes, matrices de distancia/tiempo y
    cotas para el modelo. La carpeta de destino se crea automaticamente si
    no existe.

    El archivo generado tiene el nombre "{nombre}.json" y contiene las claves:
        - "nombre"   : Nombre identificador de la instancia.
        - "n"        : Numero de clientes.
        - "D"        : Numero de dias del horizonte de planificacion.
        - "R"        : Numero de rutas (vehiculos).
        - "Q"        : Capacidad del vehiculo (con holgura aplicada).
        - "aW"       : Tiempo de apertura del deposito.
        - "bW"       : Tiempo de cierre del deposito.
        - "clientes" : Lista de clientes con todos sus campos.
        - "td"       : Matriz de distancias como lista de listas.
        - "tt"       : Matriz de tiempos de viaje como lista de listas.
        - "cotas"    : Diccionario con claves "ajustado" y "flojo", cada una
                       con lb, ub, M, M0 y Mfin calculados.

    Parametros:
    sub : dict
        Diccionario de la instancia con todos los campos necesarios (clientes,
        deposito, td, tt, Q, R, D).
    nombre : str
        Nombre base del archivo de salida (sin extension).
    carpeta : str
        Ruta de la carpeta donde se guardara el archivo JSON.
    """
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"{nombre}.json")

    # Cotas ajustadas y flojas para el Big-M
    cotas = {}
    for nivel, etiqueta in ((1, "ajustado"), (2, "flojo")):
        lb, ub = calcular_cotas(sub, nivel)
        cotas[etiqueta] = {
            "lb"  : lb.tolist(),
            "ub"  : ub.tolist(),
            "M"   : calcular_M(sub, lb, ub).tolist(),
            "M0"  : calcular_M0(sub, lb).tolist(),
            "Mfin": calcular_Mfin(sub, ub).tolist()
        }

    salida = {
        "nombre": nombre,
        "n": len(sub["clientes"]),
        "D": sub["D"],
        "R": sub["R"],
        "Q": sub["Q"],
        "aW": sub["deposito"]["a"],
        "bW": sub["deposito"]["b"],
        "clientes": sub["clientes"],
        "td": sub["td"].tolist(),
        "tt": sub["tt"].tolist(),
        "cotas": cotas
    }

    with open(ruta, "w") as f:
        json.dump(salida, f, indent=2)

def generar_instancia(ruta_txt, nombre_instancia, n_clientes, id_centro, n_dias, n_rutas, probabilidad_pedido, probabilidad_ventana, holgura, semilla, carpeta="data/instancias"):
    """
    Funcion principal que orquesta la generacion completa de una instancia del problema.

    Ejecuta en orden todas las etapas de preprocesamiento:
        1. Lee el dataset Solomon desde el archivo .txt.
        2. Selecciona un subconjunto geografico de n_clientes centrado en id_centro.
        3. Genera la demanda diaria estocastica para cada cliente.
        4. Asigna aleatoriamente ventanas de tiempo activas a cada cliente.
        5. Calcula las matrices de distancia y tiempo de viaje.
        6. Resuelve el sub-problema de capacidad minima (Q_minimo) para R rutas.
        7. Fija la capacidad del vehiculo Q aplicando la holgura indicada sobre Q_min.
        8. Guarda la instancia completa en un archivo JSON.

    Parametros:
    ruta_txt : str
        Ruta al archivo .txt con el dataset Solomon.
    nombre_instancia : str
        Nombre identificador de la instancia (usado como nombre del archivo JSON).
    n_clientes : int
        Numero de clientes a incluir en la instancia.
    id_centro : int
        ID del cliente usado como centro geografico para seleccionar el subconjunto.
    n_dias : int
        Numero de dias del horizonte de planificacion.
    n_rutas : int
        Numero de rutas (vehiculos) disponibles.
    probabilidad_pedido : float
        Probabilidad de que un cliente realice un pedido en un dia dado.
    probabilidad_ventana : float
        Probabilidad de que un cliente tenga su ventana de tiempo activa.
    holgura : float
        Factor de holgura sobre Q_min para fijar la capacidad Q
        (e.g. 0.05 implica Q = ceil(Q_min * 1.05)).
    semilla : int
        Semilla para todos los procesos aleatorios, garantiza reproducibilidad.
    carpeta : str, opcional
        Carpeta de destino para guardar el JSON (por defecto "data/instancias").

    Retorna:
    dict
        Diccionario completo de la instancia con todos los campos generados,
        listo para ser usado directamente por el modelo de optimizacion.
    """
    datos = leer_txt(ruta_txt)
    sub = elegir_subconjunto(datos, n_clientes, id_centro)
    sub = generar_pedidos(sub, n_dias, probabilidad_pedido, semilla)
    sub = asignar_ventanas(sub, probabilidad_ventana, semilla)
    sub = calcular_distancias(sub)

    # Capacidad del vehiculo
    Q_min, asignacion = Q_minimo(sub, n_rutas)
    sub["Q"] = math.ceil(Q_min * (1 + holgura))
    sub["asignacion"] = asignacion
    sub["R"] = n_rutas
    sub["D"] = n_dias

    guardar(sub, nombre_instancia, carpeta)
    print(f"{nombre_instancia}: n={n_clientes}, Q_min={Q_min}, Q={sub["Q"]}")

    return sub

if __name__ == "__main__":
    generar_instancia("data/Solomon/C101.txt", "instancia_A", n_clientes=15, id_centro=1, n_dias=3, n_rutas=3, probabilidad_pedido=0.8, probabilidad_ventana=0.6, holgura=0.05, semilla=1)
    generar_instancia("data/Solomon/R101.txt", "instancia_B", n_clientes=15, id_centro=93, n_dias=3, n_rutas=3, probabilidad_pedido=0.8, probabilidad_ventana=0.6, holgura=0.05, semilla=2)