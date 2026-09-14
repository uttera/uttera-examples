# Uttera + Asterisk

Dos AGI para usar Uttera desde un dialplan: **decir** un texto en una llamada y
**oír** lo que dice quien llama.

*[English version](README.md)*

```
agi/           hablar dentro de la llamada y oír a quien llama
recordings/    transcribir las llamadas que tu centralita ya graba
```

## `recordings/` — por aquí se empieza

Tu centralita ya está escribiendo ficheros `.wav` en algún sitio. Apunta el
guion a esa carpeta y tienes las llamadas de la semana pasada transcritas, sin
tocar Asterisk. Es el código que corremos en producción.
Ver [recordings/](recordings/).

## `agi/` — hablar dentro de la llamada

## Instalación

```bash
cp agi/uttera_agi.py /var/lib/asterisk/agi-bin/
chmod +x /var/lib/asterisk/agi-bin/uttera_agi.py
ln -s uttera_agi.py /var/lib/asterisk/agi-bin/uttera-decir.agi
ln -s uttera_agi.py /var/lib/asterisk/agi-bin/uttera-oir.agi
apt install sox            # o dnf install sox
```

La clave va en el entorno del servicio, **no en el dialplan**:

```
systemctl edit asterisk
[Service]
Environment=UTTERA_API_KEY=sk-echo-...
Environment=UTTERA_VOZ=nova
```

Una clave escrita en el dialplan acaba en la copia de seguridad de la
configuración, en el control de versiones y en la salida de `dialplan show`.

## Lo que cuesta entender la primera vez

Todo esto está resuelto en el código; se documenta porque cuesta un día
averiguarlo y cinco minutos leerlo.

**La conversión de audio no es opcional.** Uttera genera a 24 kHz y el canal
telefónico va a 8 kHz. Si le das el WAV tal cual a Asterisk, lo reproduce a su
tasa y la voz suena acelerada y aguda. Por eso `sox` convierte a `.sln` —PCM
crudo a 8 kHz—, que es exactamente lo que el canal quiere.

**Hay que añadir silencio al final.** Sin unas décimas de cola (`pad 0 0.4`),
Asterisk corta la última sílaba al cerrar el fichero.

**`STREAM FILE` va sin extensión.** Se le da el nombre base y él elige el
formato que encuentre.

**Whisper no calla ante el silencio.** Si le mandas una grabación vacía no
devuelve cadena vacía: se inventa una frase, normalmente algo como «Gracias por
ver el vídeo», porque eso abunda en su entrenamiento. El AGI descarta las
grabaciones por debajo de 2 000 bytes antes de mandarlas: te ahorra pagar por
una alucinación y, peor, actuar sobre ella.

**Las comillas de `SET VARIABLE` y `VERBOSE`.** El analizador de AGI parte por
espacios: un texto sin comillas llega partido y la variable se queda con la
primera palabra. Y una comilla *dentro* del texto descoloca el resto de la
línea, así que se sustituyen antes de mandarlo.

**Los tiempos de espera de telefonía no son los de una API.** Uttera mantiene la
conexión hasta dos horas para trabajos largos, pero aquí hay una persona con el
teléfono en la oreja: estos AGI cortan a los 30 segundos. Si Uttera no ha
contestado para entonces, la llamada ya está estropeada y lo que toca es
decirlo, no seguir esperando.

## Para transcribir llamadas ya grabadas

Eso es [`recordings/`](recordings/), y es el caso más común con diferencia.
