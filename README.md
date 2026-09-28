# 🏁 F1 Strategy Audit

Proyecto de la asignatura *Desarrollo de Aplicaciones para la Visualización de Datos* (curso 2026-2027), ICAI-ICADE, Universidad Pontificia Comillas.

Gabriela De Dorremochea

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
FastF1 / Jolpica-F1
        │
        ▼
Pipeline ETL (extracción · limpieza · variables)
        │
        ▼
PostgreSQL ──► Motor de análisis (modelo de ritmo · pit loss · simulador · Strategy Delta)
                        │
                        ▼
               Dashboard (Dash + Plotly)      [ampliación: API FastAPI · asistente IA]
```

**Limitación asumida:** el simulador no modela la interacción entre coches (tráfico, adelantamientos); la posición resultante se aproxima comparando tiempos con los rivales.

## Datos

| Fuente | Uso | Cobertura |
|---|---|---|
| [FastF1](https://docs.fastf1.dev/) | Tiempos por vuelta, neumáticos, stints, boxes, estado de pista, temperatura | 2018 – actualidad |
| [Jolpica-F1 API](https://github.com/jolpica/jolpica-f1) | Resultados, parrilla, paradas, calendario | 1950 – actualidad |

## Stack tecnológico

Python 3.11 · pandas · FastF1 · SQLAlchemy · PostgreSQL · scikit-learn · Dash / Plotly · pytest

Opcional: LightGBM · FastAPI · Docker Compose · API de un modelo de lenguaje

## Estructura prevista del repositorio

```
f1-strategy-audit/
├── README.md
├── requirements.txt
├── docker-compose.yml         # PostgreSQL
├── .env.example               # Variables de entorno
├── docs/
│   └── Propuesta.pdf          # Propuesta del proyecto
├── data/                      # Caché local de FastF1 (no se versiona)
├── notebooks/                 # Análisis exploratorio
├── src/strategy_audit/
│   ├── ingestion/             # Descarga de FastF1 y Jolpica
│   ├── processing/            # Limpieza y generación de variables
│   ├── db/                    # Modelos SQLAlchemy y carga en PostgreSQL
│   ├── models/                # Modelo de ritmo y pérdida en pit lane
│   ├── simulation/            # Simulador de estrategias y Strategy Delta
│   ├── api/                   # (Opcional) API REST con FastAPI
│   ├── dashboard/             # Aplicación Dash
│   └── assistant/             # (Opcional) Asistente de IA
└── tests/
```

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
- [ ] Base de datos con 2025 y 2026
- [ ] Modelo de ritmo validado
- [ ] Simulador validado y Strategy Delta calculado
- [ ] Dashboard MVP
- [ ] Entrega final

```


