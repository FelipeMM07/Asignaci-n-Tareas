"""
Modelo de asignación de tareas - JFV S.A.S.

Modelo general con PuLP:
    min  sum_{i,j} c[i,j] * x[i,j]
    s.a. sum_i x[i,j] = 1                      para toda tarea j
         min_t <= sum_j x[i,j] <= max_t        para todo profesional i
         x[i,j] = 0                            si i no está disponible o (i,j) está prohibida
         x[i,j] = 1                            si (i,j) es obligatoria
         x[i,j] en {0,1}

Casos:
    - Balanceado (n = m):          min_t = max_t = 1
    - Más profesionales que tareas: min_t = 0,  max_t = 1
    - Más tareas que profesionales: min_t = 0,  max_t = k (p. ej. 2)
"""

import pandas as pd
import pulp

# ---------------------------------------------------------------------------
# Datos del enunciado
# ---------------------------------------------------------------------------
PROFESIONALES = ["Ana", "Carlos", "Laura", "Miguel", "Sofía", "Andrés"]
TAREAS = ["T1", "T2", "T3", "T4", "T5", "T6"]

DESCRIPCION_TAREAS = {
    "T1": "Diseño de un sistema de control de inventarios",
    "T2": "Desarrollo de un tablero de indicadores",
    "T3": "Automatización de reportes de producción",
    "T4": "Optimización de un proceso logístico",
    "T5": "Diseño de un sistema de mantenimiento",
    "T6": "Implementación de un sistema de seguimiento de proyectos",
}

_TIEMPOS_BASE = [
    [12, 18, 15, 20, 14, 16],  # Ana
    [16, 11, 19, 14, 17, 13],  # Carlos
    [14, 16, 10, 18, 15, 17],  # Laura
    [18, 13, 16, 11, 19, 15],  # Miguel
    [15, 17, 14, 16, 9, 18],   # Sofía
    [17, 14, 18, 15, 16, 10],  # Andrés
]


def tiempos_enunciado() -> pd.DataFrame:
    """Matriz de tiempos del enunciado (horas)."""
    return pd.DataFrame(_TIEMPOS_BASE, index=PROFESIONALES, columns=TAREAS, dtype=float)


def tiempos_extendidos(n_prof: int, n_tareas: int) -> pd.DataFrame:
    """
    Matriz de tiempos de tamaño n_prof x n_tareas para la Parte 4.
    Las celdas que existen en el enunciado se conservan; las nuevas se generan
    repitiendo los datos base de forma cíclica (valores de ejemplo, editables).
    """
    nombres_p = [PROFESIONALES[i] if i < len(PROFESIONALES) else f"Profesional {i + 1}"
                 for i in range(n_prof)]
    nombres_t = [f"T{j + 1}" for j in range(n_tareas)]
    datos = []
    for i in range(n_prof):
        fila = []
        for j in range(n_tareas):
            base = _TIEMPOS_BASE[i % 6][j % 6]
            if i >= 6 or j >= 6:  # celda nueva: pequeña variación para no repetir exactamente
                base = base + ((i // 6) + (j // 6)) * 1
            fila.append(base)
        datos.append(fila)
    return pd.DataFrame(datos, index=nombres_p, columns=nombres_t, dtype=float)


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------
def resolver_asignacion(
    tiempos: pd.DataFrame,
    disponibles: dict | None = None,
    obligatorias: list | None = None,
    prohibidas: list | None = None,
    min_tareas: int = 1,
    max_tareas: int = 1,
) -> dict:
    """
    Resuelve el problema de asignación.

    Parámetros
    ----------
    tiempos      : DataFrame (profesionales x tareas) con horas estimadas.
    disponibles  : {profesional: bool}. Si es False no recibe ninguna tarea.
    obligatorias : lista de tuplas (profesional, tarea) que deben asignarse.
    prohibidas   : lista de tuplas (profesional, tarea) que no pueden asignarse.
    min_tareas   : mínimo de tareas por profesional (1 en el caso balanceado).
    max_tareas   : máximo de tareas por profesional.

    Devuelve un diccionario con estado, factibilidad, total, tablas y verificaciones.
    """
    profs = list(tiempos.index)
    tareas = list(tiempos.columns)
    disponibles = disponibles or {p: True for p in profs}
    obligatorias = list(obligatorias or [])
    prohibidas = list(prohibidas or [])

    prob = pulp.LpProblem("Asignacion_de_tareas", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("x", (profs, tareas), cat=pulp.LpBinary)

    # Función objetivo
    prob += pulp.lpSum(float(tiempos.loc[i, j]) * x[i][j] for i in profs for j in tareas)

    # Cada tarea se asigna exactamente a un profesional
    for j in tareas:
        prob += pulp.lpSum(x[i][j] for i in profs) == 1, f"Tarea_{j}"

    # Carga por profesional
    for i in profs:
        carga = pulp.lpSum(x[i][j] for j in tareas)
        if min_tareas == max_tareas:
            prob += carga == max_tareas, f"Carga_{i}"
        else:
            prob += carga <= max_tareas, f"CargaMax_{i}"
            if min_tareas > 0:
                prob += carga >= min_tareas, f"CargaMin_{i}"

    # Disponibilidad
    for i in profs:
        if not disponibles.get(i, True):
            for j in tareas:
                prob += x[i][j] == 0, f"NoDisp_{i}_{j}"

    # Prohibidas y obligatorias
    for k, (i, j) in enumerate(prohibidas):
        prob += x[i][j] == 0, f"Prohibida_{k}"
    for k, (i, j) in enumerate(obligatorias):
        prob += x[i][j] == 1, f"Obligatoria_{k}"

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    estado = pulp.LpStatus[prob.status]
    factible = estado == "Optimal"

    resultado = {
        "estado": estado,
        "factible": factible,
        "total": None,
        "asignacion": pd.DataFrame(),
        "por_profesional": pd.DataFrame(),
        "matriz": pd.DataFrame(),
        "verificacion": pd.DataFrame(),
    }
    if not factible:
        return resultado

    matriz = pd.DataFrame(
        [[int(round(x[i][j].value() or 0)) for j in tareas] for i in profs],
        index=profs, columns=tareas,
    )

    filas = []
    for i in profs:
        for j in tareas:
            if matriz.loc[i, j] == 1:
                filas.append({"Profesional": i, "Tarea": j, "Horas": float(tiempos.loc[i, j])})
    asignacion = pd.DataFrame(filas).sort_values(["Tarea"]).reset_index(drop=True)

    por_prof = []
    for i in profs:
        ts = [j for j in tareas if matriz.loc[i, j] == 1]
        por_prof.append({
            "Profesional": i,
            "Tareas asignadas": ", ".join(ts) if ts else "Sin asignación",
            "N.º de tareas": len(ts),
            "Horas": float(sum(tiempos.loc[i, j] for j in ts)),
        })
    por_prof = pd.DataFrame(por_prof)

    total = float(pulp.value(prob.objective))
    resultado.update(
        total=total,
        asignacion=asignacion,
        por_profesional=por_prof,
        matriz=matriz,
        verificacion=verificar(matriz, tiempos, disponibles, obligatorias, prohibidas,
                               min_tareas, max_tareas, total),
    )
    return resultado


def verificar(matriz, tiempos, disponibles, obligatorias, prohibidas,
              min_tareas, max_tareas, total) -> pd.DataFrame:
    """Comprueba a posteriori que la solución cumple todas las restricciones."""
    profs, tareas = list(matriz.index), list(matriz.columns)
    cargas = matriz.sum(axis=1)
    checks = [
        ("Cada tarea tiene exactamente un profesional", bool((matriz.sum(axis=0) == 1).all())),
        (f"Cada profesional recibe entre {min_tareas} y {max_tareas} tarea(s)",
         bool(((cargas >= min_tareas) & (cargas <= max_tareas)).all())),
        ("Profesionales no disponibles sin tareas",
         all(cargas[i] == 0 for i in profs if not disponibles.get(i, True))),
        ("Asignaciones obligatorias cumplidas",
         all(matriz.loc[i, j] == 1 for i, j in obligatorias)),
        ("Combinaciones prohibidas respetadas",
         all(matriz.loc[i, j] == 0 for i, j in prohibidas)),
        ("Variables binarias (0/1)", bool(matriz.isin([0, 1]).all().all())),
        ("Objetivo = suma de horas asignadas",
         abs(total - float((matriz * tiempos).sum().sum())) < 1e-6),
    ]
    return pd.DataFrame(checks, columns=["Verificación", "Cumple"]).assign(
        Cumple=lambda d: d["Cumple"].map({True: "✅ Sí", False: "❌ No"})
    )


if __name__ == "__main__":
    r = resolver_asignacion(tiempos_enunciado())
    print("Estado:", r["estado"])
    print("Suma mínima de horas:", r["total"])
    print(r["asignacion"].to_string(index=False))
    print(r["verificacion"].to_string(index=False))
