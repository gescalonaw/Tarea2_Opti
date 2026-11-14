# TC3 Optimización — conVRP-SLA reducido en Gurobi y CPLEX

Mismo modelo de la TC2 (Campelo et al., 2019), con los errores corregidos, implementado en Gurobi y en CPLEX, y comparado en ambos solvers. La comparación sigue el notebook de apoyo del ayudante (`Comparacion_Gurobi_vs_CPLEX.ipynb`): mismos comandos para relajar, mismas cuatro medidas (objetivo, tiempo, nodos y gap) y solo el límite de tiempo fijado.

**Para correr los experimentos: ver `LEEME_corridas.md`.**

## Contenido

```
LEEME_corridas.md            paso a paso para quien hace las corridas
requirements.txt             paquetes de Python
codigo/
  datos.py                   lectura de instancias, conjuntos (O, N_t, A_t, M), rutas y validación
  modelo_gurobi.py           el modelo en Gurobi: construir, relajación (Model.relax()) y entero
  modelo_cplex.py            el mismo modelo en CPLEX (docplex): construir, relajación (LinearRelaxer) y entero
  relajacion.py              corre solo la relajación continua en ambos solvers
  entero.py                  corre solo el modelo entero en ambos solvers
  correr_todo.py             CORRIDA OFICIAL: relajación + entero + tabla comparativa
  experimentos.py            funciones comunes de los tres scripts anteriores
  verificar_instalacion.py   revisa que ambos solvers tengan licencia completa
  graficar.py                gráficos de instancias y rutas
  corregir_instancia_A.py    cómo se corrigió la instancia A (reproducible)
instancias/
  instancia_A_corregida.json   20 clientes, 3 días, 3 rutas, Q = 108 (Solomon C101)
  instancia_B_corregida.json   15 clientes, 3 días, 3 rutas, Q = 75  (Solomon R101)
  C101.txt                     datos originales de Solomon usados para corregir A
figuras/                     instancias graficadas
```

## Correcciones respecto a la TC2

1. **Flujo/grado (ecs. 3–4).** En la TC2 las restricciones de entrada y salida se aplicaban a todos los clientes todos los días, aunque no pidieran. Por ejemplo, el día 1 de B piden 7 clientes y se visitaban los 15. Ahora el día t solo existen arcos entre el depósito y los clientes con pedido ese día (el conjunto A_t del paper), así que un cliente sin pedido no se visita. Las ventanas (ec. 8) también se aplican solo a pedidos.
   *Ojo:* solo quitar las ecs. 3–4 para esos clientes no basta. Si sus arcos siguen existiendo, las rutas pueden empezar o terminar en ellos y no volver al depósito. En una sub-instancia de 6 clientes, el objetivo bajaba de 124,8 a 82,6 con rutas que nunca regresaban.
2. **Instancia A.** El generador había incluido el nodo 0 de Solomon C101, que es el depósito, como "cliente 16" (distancia 0, servicio 0, demanda [0, 1, 0]). Se reemplazó por el siguiente cliente real más cercano al centro (Solomon 95), con las mismas reglas del generador, y se recalculó Q con la misma regla de la TC2 (Q = ⌈1,05·Q_min⌉ → 108).
3. **Estructura multi-día y tamaño.** Ambas instancias tienen al menos 15 clientes, 3 días y 3 rutas, y no todos piden todos los días (A: 18/14/16 pedidos por día; B: 7/13/12).

## Validación cruzada

- **Relajación:** Gurobi la resuelve con `m.update()` y `m.relax()`; CPLEX, con `LinearRelaxer.make_relaxed_model(mdl)`, que pasa X y Z a continuas en [0, 1]. Es el mismo LP, así que los objetivos deben coincidir: diferencias del orden de 1e-9 son numéricas (tolerancias de optimalidad y factibilidad). Cada LP se resuelve 5 veces y se reporta el tiempo promedio.
- **Entero:** si ambos llegan al óptimo, los objetivos deben coincidir (las rutas pueden ser distintas si hay óptimos alternativos). Si alguno corta por tiempo, se comparan objetivo, cota y gap.
- **Chequeo independiente:** cada solución entera se revisa sin usar el solver. Se verifica que todos los pedidos se atiendan una vez, que no se visite a nadie sin pedido, que cada cliente tenga la misma ruta todos los días, la capacidad, las ventanas y el regreso antes del cierre. Además, la distancia se recalcula desde las rutas.

Probado en sub-instancias de 5 y 6 clientes: z_LP y objetivo entero idénticos en Gurobi y CPLEX (diferencias ≤ 3e-14) y todas las soluciones válidas.
