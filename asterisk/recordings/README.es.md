# Transcribir las llamadas que tu centralita ya graba

*[English version](README.md)*

Es el conector que casi todo el mundo quiere, y **no hay que tocar el dialplan**.
Tu centralita ya está escribiendo ficheros `.wav` en algún sitio. Estos dos
guiones los leen.

```
transcribe-recording.sh   una grabación   → .txt + -analysis.json
bulk-reprocess.sh         una carpeta     → lo que falte por transcribir
```

Es el código que corremos en producción, sin las partes propias de nuestra
instalación.

## Dos formas de engancharlo

**Según ocurre.** MixMonitor puede lanzar un comando al empezar a grabar, así que
la transcripción está lista segundos después de colgar:

```
exten => s,n,MixMonitor(${MONITOR_FILE}.wav,b,transcribe-recording.sh ${UNIQUEID} &)
```

**A posteriori.** Una línea de cron, y en Asterisk no cambia absolutamente nada:

```
*/10 * * * * RECORDINGS_DIR=/var/spool/asterisk/monitor /opt/uttera/bulk-reprocess.sh
```

Por la segunda se empieza: apúntala a tu carpeta de grabaciones y tienes las
llamadas de la semana pasada transcritas sin haber tocado la centralita.

## Configuración

Todo por entorno, o desde `/etc/uttera/uttera.env`:

| Variable | Por defecto | |
|---|---|---|
| `UTTERA_API_KEY` | — | **Obligatoria.** Tu clave `sk-echo-…` |
| `RECORDINGS_DIR` | `/var/spool/asterisk/monitor` | Dónde están los `.wav` |
| `UTTERA_LANG` | `es` | Idioma de las llamadas |
| `UTTERA_ANALYSE` | `1` | `0` para solo transcribir |
| `FILTER` | `-mtime -7` | Qué ficheros mira `bulk-reprocess.sh` |
| `WORKERS` | `5` | Grabaciones en paralelo |

## Lo que hemos aprendido teniéndolo en marcha

**No mandes audio casi mudo.** Whisper no devuelve una cadena vacía ante el
silencio: se inventa una frase, normalmente algo como «Gracias por ver el vídeo»,
porque eso abunda en su entrenamiento. Por debajo de 1 KB se descarta. Pagarías
por una alucinación y, peor, actuarías sobre ella.

**Distingue una grabación viva de una vieja.** Mientras la llamada está en curso
MixMonitor sigue escribiendo y el fichero crece; el guion espera a que el tamaño
deje de cambiar. Para un fichero que se reprocesa esa espera es un minuto tirado
por grabación, así que todo lo que tenga más de un minuto se la salta.

**Una subida, no cuatro.** `?extras=sentiment,profile,diarize` reparte el
análisis por dentro sobre el audio que ya está ahí. Nuestra primera versión
llamaba a cada endpoint por separado y subía la misma grabación cuatro veces.

**🔴 El filtro de fecha es la línea importante de todo esto.** La primera versión
del guion por lotes no lo tenía y recorría el histórico entero en cada pasada. El
día que lo apuntamos a un archivo de verdad encoló años de llamadas de golpe y se
llevó por delante el servicio de análisis. *Un proceso por lotes cuyo tamaño
depende de cuánto tiempo lleva existiendo el sistema acabará encontrando un
tamaño que nadie probó.* Ensancha la ventana a propósito y una vez, en vez de
dejarla abierta por defecto.

**Pon un cerrojo.** Dos pasadas solapadas suben las mismas grabaciones dos veces
y se pagan dos veces.

**Más trabajadores no es más rápido.** Cada tramo de cada petición ocupa un hueco
de concurrencia de tu plan. Por encima, solo cosechas `429`.

## Qué sale

```
1234.wav              la grabación, intacta
1234.txt              la transcripción
1234-analysis.json    tono, perfil del hablante y quién habló cuándo — solo lo
                      que de verdad volvió
```

A partir de ahí es cosa tuya: meterlo en un CRM, indexarlo, resumirlo. Si lo que
quieres es un resumen y no el texto en bruto, usa `/v1/summarize`: transcribe,
analiza y resume en una sola petición.
