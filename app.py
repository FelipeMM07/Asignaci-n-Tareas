"""
App Streamlit - Asignación de tareas JFV S.A.S.
Ejecutar localmente:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

from modelo_asignacion import (
    DESCRIPCION_TAREAS,
    resolver_asignacion,
    tiempos_enunciado,
    tiempos_extendidos,
)

st.set_page_config(page_title="Asignación de tareas · JFV S.A.S.", page_icon="🧩", layout="wide")

ESTADOS = ["Libre", "Obligatoria", "Prohibida"]


# ---------------------------------------------------------------------------
# Utilidades de interfaz
# ---------------------------------------------------------------------------
def editor_tiempos(df_inicial: pd.DataFrame, key: str) -> pd.DataFrame:
    st.markdown("**Tiempos de ejecución (horas)** — filas: profesionales, columnas: tareas")
    return st.data_editor(
        df_inicial,
        key=key,
        use_container_width=True,
        num_rows="fixed",
        column_config={c: st.column_config.NumberColumn(c, min_value=0.0, step=1.0, format="%.0f")
                       for c in df_inicial.columns},
    )


def editor_disponibilidad(profs: list, key: str) -> dict:
    st.markdown("**Disponibilidad de profesionales**")
    df = pd.DataFrame({"Profesional": profs, "Disponible": True}).set_index("Profesional")
    ed = st.data_editor(df, key=key, use_container_width=True, num_rows="fixed",
                        column_config={"Disponible": st.column_config.CheckboxColumn("Disponible")})
    return ed["Disponible"].to_dict()


def editor_restricciones(profs: list, tareas: list, key: str):
    st.markdown("**Asignaciones obligatorias y combinaciones prohibidas** "
                "(elige «Obligatoria» o «Prohibida» en la celda)")
    df = pd.DataFrame("Libre", index=profs, columns=tareas)
    ed = st.data_editor(
        df, key=key, use_container_width=True, num_rows="fixed",
        column_config={t: st.column_config.SelectboxColumn(t, options=ESTADOS, required=True)
                       for t in tareas},
    )
    obligatorias = [(i, j) for i in profs for j in tareas if ed.loc[i, j] == "Obligatoria"]
    prohibidas = [(i, j) for i in profs for j in tareas if ed.loc[i, j] == "Prohibida"]
    return obligatorias, prohibidas


def mostrar_resultados(res: dict, tiempos: pd.DataFrame, max_tareas: int):
    st.subheader("Resultados")
    c1, c2 = st.columns(2)
    c1.metric("Estado del modelo", res["estado"])

    if not res["factible"]:
        c2.metric("Tiempo total mínimo", "—")
        st.error(
            f"⚠️ El modelo es **{res['estado']}** (infactible o sin solución óptima): "
            "las restricciones actuales no permiten una asignación válida. "
            "Revisa disponibilidad, asignaciones obligatorias y combinaciones prohibidas "
            "(por ejemplo, un profesional no disponible cuando todos deben recibir una tarea, "
            "dos obligatorias para la misma tarea, o una tarea con todos los profesionales prohibidos)."
        )
        return

    c2.metric("Tiempo total mínimo (h)", f"{res['total']:,.0f}")
    st.success("Solución óptima encontrada.")

    asign = res["asignacion"].copy()
    asign["Descripción"] = asign["Tarea"].map(DESCRIPCION_TAREAS).fillna("")
    st.markdown("**Asignación óptima**")
    st.dataframe(asign, use_container_width=True, hide_index=True)

    st.markdown("**Tiempo por profesional**")
    st.dataframe(res["por_profesional"], use_container_width=True, hide_index=True)

    st.markdown("**Matriz binaria de asignaciones (x_ij)**")
    st.dataframe(res["matriz"], use_container_width=True)

    st.markdown("**Verificación de restricciones**")
    st.dataframe(res["verificacion"], use_container_width=True, hide_index=True)

    sin_tarea = res["por_profesional"].query("`N.º de tareas` == 0")["Profesional"].tolist()
    if sin_tarea:
        st.info("Profesionales sin asignación: " + ", ".join(sin_tarea))


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
st.title("🧩 Asignación óptima de tareas · JFV S.A.S.")
st.caption("Minimiza la suma de horas de trabajo con programación lineal entera (PuLP + CBC). "
           "Los datos iniciales son los del enunciado (+1000 h en cada tiempo) y sin restricciones adicionales.")

tab3, tab4 = st.tabs(["Parte 3 · Asignación balanceada (6×6)", "Parte 4 · Asignación no balanceada"])

# ------------------------------ Parte 3 ------------------------------------
with tab3:
    base = tiempos_enunciado()
    profs, tareas = list(base.index), list(base.columns)

    col_a, col_b = st.columns([3, 2])
    with col_a:
        tiempos = editor_tiempos(base, key="t3_tiempos")
    with col_b:
        disponibles = editor_disponibilidad(profs, key="t3_disp")

    obligatorias, prohibidas = editor_restricciones(profs, tareas, key="t3_restr")

    with st.expander("Descripción de las tareas"):
        for t, d in DESCRIPCION_TAREAS.items():
            st.write(f"**{t}**: {d}")

    if st.button("Optimizar asignación", type="primary", key="t3_btn"):
        res = resolver_asignacion(tiempos, disponibles, obligatorias, prohibidas,
                                  min_tareas=1, max_tareas=1)
        mostrar_resultados(res, tiempos, 1)

# ------------------------------ Parte 4 ------------------------------------
with tab4:
    st.markdown("Modifica el número de profesionales y de tareas. "
                "Los valores de las filas/columnas que no están en el enunciado son de ejemplo y se pueden editar.")

    preset = st.radio(
        "Escenario",
        ["Personalizado", "A · 7 profesionales y 5 tareas", "B · 5 profesionales y 7 tareas"],
        horizontal=True, key="t4_preset",
    )
    if preset.startswith("A"):
        n_prof_def, n_tar_def = 7, 5
    elif preset.startswith("B"):
        n_prof_def, n_tar_def = 5, 7
    else:
        n_prof_def, n_tar_def = 6, 6

    c1, c2, c3 = st.columns(3)
    n_prof = c1.number_input("Número de profesionales", 1, 15, n_prof_def, key=f"t4_np_{preset}")
    n_tar = c2.number_input("Número de tareas", 1, 15, n_tar_def, key=f"t4_nt_{preset}")

    if n_prof > n_tar:
        modo = "A"
        min_t, max_t = 0, 1
        st.info("Más profesionales que tareas: cada tarea a un profesional, cada profesional "
                "**como máximo 1** tarea (los sobrantes quedan sin asignación).")
        c3.number_input("Máx. tareas por profesional", 1, 1, 1, disabled=True, key="t4_max_a")
    elif n_prof < n_tar:
        modo = "B"
        max_t = c3.number_input("Máx. tareas por profesional", 1, 10, 2, key="t4_max_b")
        min_t = 0
        if max_t * n_prof < n_tar:
            st.warning("Con ese máximo no alcanza la capacidad para cubrir todas las tareas (infactible).")
        st.info(f"Más tareas que profesionales: todas las tareas se asignan y cada profesional "
                f"recibe **como máximo {max_t}**.")
    else:
        modo = "bal"
        min_t, max_t = 1, 1
        st.info("Caso balanceado: cada profesional recibe exactamente una tarea.")
        c3.number_input("Máx. tareas por profesional", 1, 1, 1, disabled=True, key="t4_max_bal")

    n_prof, n_tar = int(n_prof), int(n_tar)
    base4 = tiempos_extendidos(n_prof, n_tar)
    profs4, tareas4 = list(base4.index), list(base4.columns)
    sig = f"{preset}_{n_prof}_{n_tar}"

    col_a, col_b = st.columns([3, 2])
    with col_a:
        tiempos4 = editor_tiempos(base4, key=f"t4_tiempos_{sig}")
    with col_b:
        disp4 = editor_disponibilidad(profs4, key=f"t4_disp_{sig}")
    obl4, proh4 = editor_restricciones(profs4, tareas4, key=f"t4_restr_{sig}")

    if st.button("Optimizar asignación", type="primary", key="t4_btn"):
        res = resolver_asignacion(tiempos4, disp4, obl4, proh4, min_tareas=min_t, max_tareas=int(max_t))
        mostrar_resultados(res, tiempos4, int(max_t))
