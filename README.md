# 🏁 F1 Strategy Audit

Proyecto de la asignatura *Desarrollo de Aplicaciones para la Visualización de Datos* (curso 2026-2027), ICAI-ICADE, Universidad Pontificia Comillas.

Gabriela De Dorremochea

**Aplicación desplegada:** https://f1-strategy-audit.onrender.com/

---

## Descripción

En Fórmula 1 la estrategia decide carreras: cuándo parar y con qué neumático. Fuera de los equipos, esas decisiones se juzgan con intuición y opinión, no con datos.

**F1 Strategy Audit** es una aplicación interactiva que, después de cada Gran Premio:

1. **Modela el ritmo** de cada piloto (degradación del neumático y efecto del combustible) a partir de los tiempos por vuelta.
2. **Simula estrategias alternativas** (otra vuelta de parada, otros compuestos, una o dos paradas) y calcula el tiempo total de carrera resultante.
3. **Cuantifica la calidad de cada decisión** con la métrica *Strategy Delta*: segundos ganados o perdidos frente a la mejor estrategia simulada.
4. **Lo visualiza** en un dashboard con análisis de carrera, simulador "¿y si…?" y balance de temporada.

Usuarios objetivo: aficionados avanzados, periodistas y creadores de contenido, y estudiantes o aspirantes a ingenieros de estrategia.

## Objetivos

**Minimum Viable Product**

- **O1 · Datos:** pipeline reproducible que integre FastF1 y Jolpica-F1 en PostgreSQL (temporadas 2025 y 2026, carreras en seco).
- **O2 · Modelo de ritmo:** regresión por compuesto y circuito que estime la degradación y el efecto del combustible, validada con MAE sobre carreras no usadas en el ajuste.
- **O3 · Simulador:** cálculo del tiempo total de carrera de un piloto para estrategias de una y dos paradas, validado frente a los tiempos reales.
- **O4 · Auditoría:** métrica *Strategy Delta* por piloto, carrera, equipo y temporada.
- **O5 · Visualización:** dashboard en Dash/Plotly con tres vistas (carrera, "¿y si…?", temporada).

**Ampliaciones opcionales (después de terminar el MVP)**

- API REST con FastAPI · asistente de IA que explique los resultados · reacción ante Safety Car / VSC · modelo LightGBM · simulación Monte Carlo con incertidumbre.

## Arquitectura

```
FastF1 (tiempos por vuelta, neumáticos, boxes, estado de pista)
        │   scripts/download_data.py   (necesita Internet, carga incremental)
        ▼
data/raw/*.parquet
        │   scripts/build_dataset.py   (sin conexión)
        ▼
Limpieza ─► Modelo de ritmo ─► Pérdida en boxes ─► Simulador ─► Strategy Delta
        │
        ▼
data/processed/*.parquet  ──►  Dashboard Dash + Plotly  ──►  Render (URL pública)
```

**Decisión de diseño (noviembre 2026):** la propuesta preveía PostgreSQL. Como todo el cálculo
pesado se hace *offline* y la aplicación solo lee resultados, se sustituye por ficheros Parquet
versionados en el repositorio. Ventajas: despliegue gratuito y sin servicios externos en Render,
arranque rápido y resultados reproducibles. PostgreSQL queda como ampliación.

**Limitación asumida:** el simulador no modela la interacción entre coches (tráfico, adelantamientos); la posición resultante se aproxima comparando tiempos con los rivales.

## Datos

| Fuente | Uso | Cobertura |
|---|---|---|
| [FastF1](https://docs.fastf1.dev/) | Tiempos por vuelta, neumáticos, stints, boxes, estado de pista, temperatura | 2018 – actualidad |
| [Jolpica-F1 API](https://github.com/jolpica/jolpica-f1) | Resultados, parrilla, paradas, calendario | 1950 – actualidad |

## Stack tecnológico

Python 3.12 · pandas · NumPy · FastF1 · Parquet (pyarrow) · Dash / Plotly · pytest · gunicorn · Render

## Estructura del repositorio

```
F1-Strategy-Audit/
├── app.py                     # Punto de entrada (local y gunicorn en Render)
├── requirements.txt           # Dependencias de la app (Render)
├── requirements-pipeline.txt  # + FastF1, scikit-learn, pytest (local)
├── Procfile · render.yaml     # Despliegue en Render
├── assets/style.css           # Estilos del dashboard
├── data/
│   ├── raw/                   # Datos descargados con FastF1 (Parquet)
│   └── processed/             # Tablas que consume la app (Parquet)
├── docs/                      # Propuesta
├── scripts/
│   ├── download_data.py       # Paso 1: descarga
│   └── build_dataset.py       # Paso 2: modelo, simulación y auditoría
├── src/strategy_audit/
│   ├── ingestion/             # Descarga con FastF1
│   ├── processing/            # Limpieza, stints, vueltas con SC/VSC
│   ├── models/                # Modelo de ritmo y pérdida en boxes
│   ├── simulation/            # Simulador de estrategias y Strategy Delta
│   ├── dashboard/             # Datos, tema visual (theme.py), figuras, layout y callbacks de Dash
│   └── pipeline.py            # Orquestación del paso 2
└── tests/                     # pytest con carreras sintéticas de parámetros conocidos
```

## Cómo ejecutarlo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-pipeline.txt

python scripts/download_data.py --season 2025   # descarga (≈15 min la primera vez)
python scripts/build_dataset.py --season 2025   # modelo + auditoría
python app.py                                   # http://127.0.0.1:8050
pytest                                          # tests
```

## Resultados (temporada 2025)

| Métrica | Valor |
|---|---|
| Carreras auditadas (en seco) | 21 de 24 |
| Auditorías piloto-carrera | 351 |
| Error del modelo de ritmo (MAE, stints no vistos) | 0,52 s por vuelta |
| Error del simulador con la estrategia real (carreras sin SC) | 2,2 s en el tiempo total (≈ 0,04 %) |

## Método

| Paso | Qué hace |
|---|---|
| Limpieza | Excluye vuelta 1, vueltas de entrada/salida de boxes, SC/VSC/roja, atípicas (> 5 % sobre la mediana del piloto) y carreras con lluvia |
| Modelo de ritmo | Por carrera: `tiempo = ritmo piloto + offset compuesto + degradación compuesto × edad neumático + combustible × vuelta` (mínimos cuadrados). Validación cruzada dejando fuera stints completos |
| Pérdida en boxes | Mediana del tiempo extra de vueltas de entrada + salida frente al modelo, con bandera verde. Con SC/VSC cuenta la mitad |
| Reglas 2025 | Dos paradas obligatorias en Mónaco y máximo de 25 vueltas por juego en Qatar |
| Simulador | Todas las estrategias de 1 y 2 paradas que usan ≥ 2 compuestos y no superan el stint más largo observado; vectorizado con NumPy |
| Strategy Delta | Tiempo simulado con la estrategia real − tiempo simulado con la mejor. Posición estimada frente a los tiempos reales de los rivales |

## Plan de trabajo inicial

Planificación para un cuatrimestre (10 semanas desde la propuesta).

| Fase | Semanas | Tareas | Entregable |
|---|---|---|---|
| **0. Propuesta** | 1 | Definición del proyecto, repositorio y README | Propuesta (5 oct 2026) |
| **1. Datos** | 2 | Descarga con FastF1 y Jolpica, limpieza de vueltas, esquema y carga en PostgreSQL, EDA de degradación | Base de datos 2025–2026 y notebook de EDA |
| **2. Modelo de ritmo** | 2-4 | Regresión por compuesto y circuito, pérdida en pit lane, validación (MAE) | Modelo validado |
| **3. Simulador y auditoría** | 5-6 | Simulador de 1 y 2 paradas, validación frente a tiempos reales, cálculo del Strategy Delta | Auditoría de todas las carreras |
| **4. Dashboard** | 7-8 | Vistas de carrera, «¿y si…?» y temporada en Dash | Aplicación funcional (MVP) |
| **5. Cierre** | 9-10 | Pruebas, documentación, memoria y presentación; ampliaciones si hay margen | Entrega final |

### Hitos

- [x] Propuesta y repositorio
- [x] Pipeline de datos y modelo implementados (2025)
- [x] Datos reales 2025 descargados (24 carreras, 26 689 vueltas) y modelo validado
- [x] Simulador y Strategy Delta (con tests)
- [x] Dashboard MVP (carrera, ¿y si…?, temporada, metodología)
- [x] Aplicación desplegada en una URL pública (Render)
- [ ] Presentación (26/30 nov 2026)
- [ ] Ampliaciones: temporada 2026, PostgreSQL, API, asistente IA



