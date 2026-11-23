# 🏁 F1 Strategy Audit

[![Tests](https://github.com/gabrieladorre-design/F1-Strategy-Audit/actions/workflows/tests.yml/badge.svg)](https://github.com/gabrieladorre-design/F1-Strategy-Audit/actions/workflows/tests.yml)

**App:** https://f1-strategy-audit.onrender.com/ (si tarda ~50 s en abrir es que Render la había dormido)

Proyecto de *Desarrollo de Aplicaciones para la Visualización de Datos* (2026-2027), ICAI-ICADE · Gabriela de Dorremochea

---

## La idea

Después de cada Gran Premio siempre surge la misma discusión: «Ferrari volvió a equivocarse con la estrategia». Pero casi nunca se mide de verdad cuánto costó esa decisión.

Este proyecto intenta medirlo. Para cada piloto de cada carrera de 2025 se pregunta: **¿cuántos segundos perdió por cómo gestionó paradas y neumáticos, comparado con lo mejor que podría haber hecho?** A ese número lo llamo **Strategy Delta**.

**Para empezar, tres vistas que merecen la pena:**
- [Mónaco con Verstappen](https://f1-strategy-audit.onrender.com/?vista=carrera&gp=MON&piloto=VER): sin contar el tráfico parecía que había perdido 15 s; con tráfico, su estrategia fue la mejor posible, porque cualquier otra le habría hecho salir de boxes detrás de Leclerc y Norris.
- [¿Y si…? en Singapur con Norris](https://f1-strategy-audit.onrender.com/?vista=ysi&gp=SGP&piloto=NOR): perdió 24 s atascado detrás de otros coches; mueve la parada y mira detrás de quién habría salido.
- [La temporada de Ferrari](https://f1-strategy-audit.onrender.com/?vista=temporada&equipo=Ferrari): cómo de bien acertó con la estrategia frente al resto de equipos.

## Cómo funciona

Todo el cálculo pesado se hace una vez, en local. La app solo lee los resultados ya calculados, por eso arranca rápido y se puede alojar gratis.

```
FastF1 ─► limpieza ─► modelo de ritmo ─► pérdida en boxes ─► tráfico ─► simulador ─► Strategy Delta ─► dashboard
          (scripts/download_data.py)     (scripts/build_dataset.py, sin Internet)                       (app.py)
```

**1. Datos.** Con [FastF1](https://docs.fastf1.dev/) descargo, vuelta a vuelta, el tiempo, el neumático, su edad, las paradas y si había Safety Car. Para estimar el ritmo me quedo solo con vueltas «limpias»: fuera la salida, las vueltas de entrada y salida de boxes, las de SC/VSC y las anormalmente lentas. Además marco las vueltas que empezaron con otro coche a menos de 1,5 s delante («en tráfico»). Las carreras con lluvia o con datos de neumáticos incompletos se descartan enteras.

**2. Modelo de ritmo.** Para cada carrera ajusto una regresión lineal:

> tiempo de vuelta = ritmo del piloto + efecto del compuesto + degradación × edad del neumático + combustible × nº de vuelta + coste de ir en tráfico

Así sé, en cada circuito, cuánto más rápido es un compuesto que otro y cuánto pierde por cada vuelta de uso. El último término es clave: separa el ritmo de cada piloto en aire limpio de lo que pierde por ir detrás de otro coche (unos 0,3 s por vuelta de media). Lo valido dejando fuera stints enteros y prediciéndolos: se equivoca de media **0,50 s por vuelta**.

**3. Pérdida en boxes.** Miro cuánto más lentas son las vueltas de entrada y salida de cada parada respecto a lo que predice el modelo, y me quedo con la mediana (unos 18–28 s según el circuito). Si paras con SC o VSC, cuento la mitad.

**4. Tráfico.** Una parada puede ser rápida en el papel y dejarte detrás de un coche más lento al salir. Para tenerlo en cuenta, dejo a los rivales exactamente como corrieron de verdad y muevo solo al piloto que estudio. Vuelta a vuelta comparo su tiempo acumulado con el de los demás: si va a alcanzar a alguien, solo lo adelanta si esa vuelta es claramente más rápido (más que un umbral propio de cada circuito); si no, se queda detrás y pierde ese tiempo. El umbral sale de la propia carrera: miro todas las veces que un coche fue a menos de 1 s de otro y lo ajusto para que el modelo adelante en la misma proporción que hubo adelantamientos reales. Sale 3 s por vuelta en Mónaco y 0,9 s en Monza.

**5. Simulador.** Con el modelo, la pérdida en boxes y el tráfico puedo calcular el tiempo total de cualquier estrategia. Pruebo todas las de 1 y 2 paradas que cumplen el reglamento (dos compuestos distintos, y en 2025 dos paradas obligatorias en Mónaco y máximo 25 vueltas por juego en Qatar) sin pasarme de la longitud de stint que se vio en carrera. Para encontrar la mejor sin simular el tráfico de las ~70 000 combinaciones, las recorro de más rápida a más lenta en pista libre y paro cuando ninguna de las que quedan puede ganar (el tráfico solo suma tiempo). Con la estrategia real y sin tráfico, el simulador iba 7,3 s por delante de la realidad; con tráfico, el sesgo baja a **+0,2 s** y el error típico es de **1,7 s** en hora y media de carrera.

**6. Strategy Delta.** Simulo la estrategia que hizo el piloto y la mejor posible, las dos con tráfico, y resto. Como las dos salen del mismo modelo, sus errores se compensan casi del todo y lo que queda es el efecto de la decisión. Además estimo en qué posición habría acabado comparando su tiempo corregido con los tiempos reales de los rivales.

## Qué vas a ver en la app

| Pestaña | Para qué sirve |
|---|---|
| **Análisis de carrera** | Eliges un GP y ves los stints reales frente a los óptimos, la evolución de la carrera, quién perdió más tiempo y cuánto se degradó cada compuesto |
| **¿Y si…?** | Cambias neumáticos y vueltas de parada de un piloto y ves al momento cuánto habría ganado o perdido, en qué posición habría acabado, detrás de quién habría salido de boxes y cuánto tiempo habría perdido en tráfico. También muestra la ventana de parada: entre qué vueltas parar costaba menos de 1 s |
| **Temporada** | Ranking de equipos por acierto estratégico (con intervalo de confianza), posiciones perdidas por piloto y la carrera más difícil de acertar |
| **Metodología** | Cómo de bien funciona el modelo, lo difícil que es adelantar en cada circuito y lo que no tiene en cuenta |

**Enlaces directos.** El botón «Copiar enlace a esta vista» guarda la carrera, el piloto o el equipo que tengas elegidos. Por ejemplo, [`?vista=carrera&gp=MON&piloto=VER`](https://f1-strategy-audit.onrender.com/?vista=carrera&gp=MON&piloto=VER) abre Mónaco con Verstappen destacado, y [`?vista=temporada&equipo=Ferrari`](https://f1-strategy-audit.onrender.com/?vista=temporada&equipo=Ferrari) abre la temporada de Ferrari. En la pestaña de carrera, «Descargar CSV» baja la auditoría de ese GP, lista para abrir en Excel.

**Para presentaciones**, al pasar el ratón por cualquier gráfico aparece un icono de cámara que lo descarga en PNG a doble resolución. Y si compartes el enlace en LinkedIn o WhatsApp, sale con imagen y descripción.

**En el móvil** también se usa bien: las pestañas se deslizan en una fila y cada gráfico se desplaza en horizontal, así que nada queda aplastado.

Los títulos de cada gráfico no describen el gráfico, cuentan la conclusión (p. ej. «Norris perdió 14,6 s con B → M → B → B frente a M → B → B» en España), y cambian según lo que elijas.

## Resultados 2025

- **20 de 24 carreras** auditadas y **348** auditorías piloto-carrera.
- Fuera quedan Australia, Gran Bretaña y Bélgica (lluvia) y Miami (FastF1 no trae los neumáticos de las primeras 24 vueltas y el resto llega desalineado).
- Error del modelo: 0,50 s por vuelta en stints que no vio al ajustarse.
- Error del simulador con tráfico: 1,7 s típico en el tiempo total y sesgo de +0,2 s (carreras sin Safety Car).
- El tráfico cambia la conclusión: solo en el 22 % de los casos la mejor estrategia es la misma que sin tráfico. De media, la estrategia real perdió 7,4 s atascada detrás de otros coches y la mejor, 3,4 s.

## Lo que el modelo no sabe

Prefiero decirlo claro antes de que salga en las preguntas:

- **Los rivales no reaccionan.** Si el piloto hubiera parado antes, los demás habrían corrido igual: no le cubren ni se ven frenados por él. Y el adelantamiento es todo o nada (si tiene ritmo pasa, si no se queda detrás).
- **Es a posteriori.** La mejor estrategia «sabe» cuándo salió el Safety Car; el muro no lo sabía.
- **Neumático nuevo en cada parada.** No sé qué juegos le quedaban a cada piloto.
- **Degradación lineal**, sin calentamiento del neumático ni salida. Por eso el modelo tiende a preferir empezar con duro.
- **Imprevistos.** Averías, toques o problemas de frenos explican los errores más grandes del simulador; ningún modelo de estrategia los prevé.

## Ejecutarlo en local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-pipeline.txt

python app.py                                   # la app, con los datos que ya hay en el repo → http://127.0.0.1:8050
pytest                                          # tests

# Solo si quieres regenerar los datos:
python scripts/download_data.py --season 2025   # descarga de FastF1 (~15 min la primera vez)
python scripts/build_dataset.py --season 2025   # modelo, simulación y auditoría (segundos)
```

## Cómo está organizado

```
app.py                       punto de entrada (local y Render)
scripts/                     download_data.py (descarga) y build_dataset.py (cálculo)
src/strategy_audit/
  ingestion/                 descarga con FastF1
  processing/                limpieza de vueltas, stints y vueltas con SC/VSC
  models/                    modelo de ritmo y pérdida en boxes
  simulation/                simulador de estrategias y Strategy Delta
  dashboard/                 datos, estilo (theme.py), figuras, layout y callbacks de Dash
  pipeline.py                une todos los pasos del cálculo
data/raw/ · data/processed/  Parquet: datos descargados y tablas que lee la app
tests/                       pytest con carreras sintéticas de parámetros conocidos
```

**Stack:** Python 3.12 · pandas · NumPy · FastF1 · Parquet · Dash + Plotly · pytest · gunicorn · Render · GitHub Actions

## Despliegue

- Cada `git push` a `main` lanza los tests en GitHub Actions y vuelve a desplegar la app en Render.
- Qué commit está en línea se ve en el panel de Render (Events).
- Si después de un despliegue algo da error, recarga con Cmd + Shift + R: la pestaña abierta seguía con la versión anterior.

## Por qué no hay base de datos

La propuesta inicial usaba PostgreSQL. Al ver que la app solo lee resultados ya calculados, lo cambié por ficheros Parquet dentro del repo: despliegue gratis, sin servicios externos y resultados reproducibles por cualquiera que clone el proyecto. Si el proyecto crece (temporada 2026, API), es lo primero que volvería a poner.
