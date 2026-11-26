# F1 Strategy Audit

**¿Cuánto tiempo le costó a cada piloto su estrategia en la temporada 2025 de Fórmula 1?**

**Aplicación:** [f1-strategy-audit.onrender.com](https://f1-strategy-audit.onrender.com/)

La primera carga puede tardar alrededor de un minuto, porque el servidor gratuito se pone en pausa cuando nadie lo usa. Después funciona con normalidad.

**Presentación:** [docs/F1_Strategy_Audit_Presentacion.pptx](docs/F1_Strategy_Audit_Presentacion.pptx)

Gabriela de Dorremochea · Proyecto de la asignatura *Desarrollo de Aplicaciones para la Visualización de Datos* · ICAI-ICADE, curso 2026-2027

---

## ¿De qué va esto?

Cada domingo, después de la carrera, alguien dice: «Ferrari la ha vuelto a liar con la estrategia». Pero casi nadie lo mide.

Yo he querido medirlo. Para cada piloto en cada carrera de 2025 me pregunto:

> **¿Cuántos segundos perdió por cuándo paró y qué neumáticos puso, comparado con lo mejor que podría haber hecho?**

A ese número le llamo **Strategy Delta**. Si es 0, la estrategia fue perfecta. Si es 20, el muro le costó 20 segundos.

## Objetivos

- Medir con datos cuánto acertó cada equipo con la estrategia, en lugar de quedarse en la opinión.
- Dejar que cualquiera pruebe estrategias alternativas y vea al momento qué habría pasado.
- Publicarlo como una aplicación web que se pueda usar y compartir sin instalar nada.

## Cómo funciona, sin tecnicismos

1. **Descargo los datos** de cada vuelta con [FastF1](https://docs.fastf1.dev/): tiempo, neumático, cuántas vueltas lleva, paradas y Safety Car.
2. **Aprendo el ritmo de cada carrera.** Con una regresión sencilla saco cuánto va más rápido cada compuesto, cuánto se degrada por vuelta, cuánto ayuda quemar gasolina y cuánto se pierde yendo detrás de otro coche (unos 0,3 s por vuelta).
3. **Calculo lo que cuesta parar** en cada circuito (entre 18 y 28 s). Con Safety Car, la mitad.
4. **Meto el tráfico.** Los rivales corren exactamente como corrieron de verdad; solo muevo al piloto que estudio. Si alcanza a alguien, solo le adelanta si va claramente más rápido. Ese «claramente» depende del circuito: en Mónaco hacen falta 3 s por vuelta, en Monza 0,9 s.
5. **Pruebo todas las estrategias** de 1 y 2 paradas que permite el reglamento y me quedo con la más rápida.
6. **Resto:** lo que hizo menos lo mejor posible = Strategy Delta.

Todo esto se calcula una vez en mi ordenador. La app solo enseña los resultados, por eso abre rápido y se puede alojar gratis.

## ¿Qué hay en la app?

| Pestaña | Qué puedes hacer |
|---|---|
| **Análisis de carrera** | Elegir un GP y ver qué hizo cada piloto frente a lo ideal, quién perdió más y cómo se gastó cada neumático |
| **¿Y si…?** | Cambiar tú la estrategia de un piloto y ver al momento cuánto habría ganado o perdido, en qué posición habría acabado y detrás de quién habría salido |
| **Temporada** | Ver qué equipos aciertan más con la estrategia y qué pilotos perdieron más posiciones |
| **Metodología** | Ver cómo de fiable es el modelo y lo que no tiene en cuenta |

Algunos detalles que me parecían útiles:

- **Enlaces directos:** el botón «Copiar enlace» guarda la carrera, el piloto o el equipo que tengas elegidos, para mandárselo a alguien.
- **Descargas:** la auditoría de cada carrera en CSV (se abre bien en Excel) y cualquier gráfico en PNG con el icono de la cámara.
- **Móvil:** se usa bien; las pestañas y los gráficos se deslizan de lado.
- **Títulos que cuentan algo:** en vez de «Stints por piloto», pone por ejemplo «Norris perdió 14,6 s con B → M → B → B».
- **Aspecto de F1:** rojo, blanco y negro carbono, la tipografía Titillium Web y el logo en la cabecera.

## Lo que ha salido

- **20 de las 24 carreras** de 2025 y **348** análisis piloto-carrera.
- En total, **64 minutos** perdidos por estrategia en la temporada. Solo un **11 %** de las estrategias fueron casi perfectas.
- **El tráfico lo cambia todo:** en el 78 % de los casos, la mejor estrategia con tráfico no es la misma que sin él.
- **¿Es fiable?** El modelo se equivoca de media 0,5 s por vuelta. Repitiendo la carrera real, el simulador acaba a 1,7 s de la realidad en hora y media de carrera.

## Decisiones que he ido tomando

Por el camino he cambiado varias cosas respecto a la propuesta. Estas son las importantes y por qué:

- **Sin base de datos.** La propuesta tenía PostgreSQL, pero la app solo lee resultados ya calculados. Con ficheros Parquet en el repo, el despliegue es gratis y cualquiera puede reproducirlo. Si el proyecto crece, es lo primero que volvería a poner.
- **Solo 2025.** Mejor una temporada bien hecha que varias a medias.
- **Un modelo sencillo.** Una regresión lineal por carrera: se entiende, se explica en dos minutos y funciona bien.
- **Reglas reales de 2025.** Dos paradas obligatorias en Mónaco y máximo 25 vueltas por juego de neumáticos en Qatar.
- **Fuera las carreras con datos malos.** Australia, Gran Bretaña y Bélgica por lluvia, y Miami porque a FastF1 le faltan los neumáticos de las primeras 24 vueltas. Descarto cualquier carrera con más de un 5 % de vueltas sin neumático conocido.
- **Añadir el tráfico.** Al principio el simulador ignoraba a los demás coches y salía 7 s más rápido que la realidad. Con tráfico, la diferencia baja a 0,2 s. Fue el cambio que más mejoró el proyecto.
- **Una app que se comparte.** Enlaces directos, vista previa al compartirla en WhatsApp o LinkedIn, versión móvil y descargas.
- **Estilo propio de F1.** Colores, tipografía y logo para que se reconozca a primera vista.
- **Tests y despliegue automático.** Cada cambio pasa los tests en GitHub Actions antes de publicarse en Render.

## Lo que el modelo no sabe

Mejor decirlo yo antes de que me lo pregunten:

- **Los rivales no reaccionan.** Si el piloto hubiera parado antes, los demás habrían hecho lo mismo que hicieron.
- **Juega con ventaja.** La mejor estrategia ya sabe cuándo salió el Safety Car; el muro no lo sabía.
- **Neumáticos nuevos en cada parada.** No sé qué juegos le quedaban a cada uno.
- **Degradación en línea recta.** No tiene en cuenta que el neumático tarda en calentarse.
- **Averías y toques.** Ningún modelo de estrategia los ve venir.

## Dónde está cada cosa

```
app.py              arranca la app
scripts/            descarga de datos y cálculo
src/strategy_audit/
  ingestion/        descarga con FastF1
  processing/       limpieza de vueltas y Safety Car
  models/           ritmo y coste de parar
  simulation/       simulador, tráfico y Strategy Delta
  dashboard/        la app: gráficos, estilo y pantallas
assets/             estilos, logo e icono
data/               los datos en Parquet
tests/              tests con carreras inventadas
docs/               la propuesta inicial y la presentación
```
