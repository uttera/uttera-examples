#!/usr/bin/env python3
"""Uttera desde Asterisk: decir un texto y escuchar al que llama.

Dos AGI en un fichero, porque comparten todo salvo diez lineas:

    uttera-decir.agi   "texto a decir"      -> lo reproduce en la llamada
    uttera-oir.agi     [segundos] [idioma]  -> graba, transcribe y deja el texto
                                               en la variable de canal UTTERA_TEXTO

Sin dependencias: urllib de la biblioteca estandar. Necesita `sox` en el sistema
para convertir el audio, que es lo unico que Asterisk no hace por si mismo.

    export UTTERA_API_KEY=sk-echo-...
    ln -s uttera_agi.py /var/lib/asterisk/agi-bin/uttera-decir.agi
    ln -s uttera_agi.py /var/lib/asterisk/agi-bin/uttera-oir.agi
"""
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
import uuid

API   = os.environ.get("UTTERA_API", "https://api.uttera.ai")
CLAVE = os.environ.get("UTTERA_API_KEY", "")
VOZ   = os.environ.get("UTTERA_VOZ", "nova")
# La regla de las dos horas no aplica en telefonia: aqui hay alguien esperando
# al otro lado del telefono. Si Uttera no contesta en 30 s, la llamada ya se ha
# estropeado y lo que toca es decirlo, no seguir esperando.
ESPERA = int(os.environ.get("UTTERA_TIMEOUT", "30"))
# Donde deja los ficheros temporales. TIENE que ser legible por Asterisk.
SONIDOS = os.environ.get("UTTERA_SOUNDS", "/var/lib/asterisk/sounds/uttera")


# ── protocolo AGI ───────────────────────────────────────────────────────────
# Asterisk habla por stdin/stdout: primero vuelca el entorno (una linea por
# variable, linea en blanco al final) y despues espera comandos.
def leer_entorno():
    env = {}
    while True:
        linea = sys.stdin.readline().strip()
        if not linea:
            return env
        if ":" in linea:
            k, v = linea.split(":", 1)
            env[k.strip()] = v.strip()


def agi(orden):
    """Manda un comando y devuelve el codigo de resultado."""
    sys.stdout.write(orden + "\n")
    sys.stdout.flush()
    respuesta = sys.stdin.readline().strip()
    return respuesta


def verbose(texto):
    # ⚠ Las comillas son OBLIGATORIAS y el texto no puede llevarlas dentro: el
    # analizador de AGI parte por espacios y una comilla suelta descoloca el
    # resto de la linea.
    agi('VERBOSE "%s" 1' % texto.replace('"', "'"))


def peticion(ruta, datos=None, cabeceras=None, metodo="POST"):
    req = urllib.request.Request(API + ruta, data=datos, method=metodo)
    req.add_header("Authorization", "Bearer " + CLAVE)
    for k, v in (cabeceras or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=ESPERA) as r:
        return r.read(), dict(r.headers)


# ── decir ───────────────────────────────────────────────────────────────────
def decir(texto, idioma="es"):
    import json
    cuerpo = json.dumps({"model": "tts-1", "voice": VOZ, "input": texto,
                         "language": idioma, "response_format": "wav"}).encode()
    audio, _ = peticion("/v1/audio/speech", cuerpo,
                        {"Content-Type": "application/json"})

    os.makedirs(SONIDOS, exist_ok=True)
    base = os.path.join(SONIDOS, "u-" + uuid.uuid4().hex[:12])
    crudo = base + ".src.wav"
    with open(crudo, "wb") as f:
        f.write(audio)

    # ⚠ La conversion NO es opcional. Uttera genera a 24 kHz y el canal
    # telefonico va a 8 kHz: Asterisk reproduciria el fichero a su tasa y la voz
    # sonaria acelerada y aguda. `sln` es PCM crudo a 8 kHz, que es justo lo que
    # el canal quiere y evita una segunda conversion en vivo.
    #
    # ⚠ El `pad 0 0.4` de cola tampoco es un adorno: sin unas decimas de
    # silencio al final, Asterisk corta la ultima silaba al cerrar el fichero.
    subprocess.run(["sox", crudo, "-r", "8000", "-c", "1", "-t", "raw",
                    base + ".sln", "pad", "0", "0.4"], check=True)
    os.unlink(crudo)

    # STREAM FILE va SIN extension: Asterisk elige el formato que mejor le venga
    # de entre los que encuentre con ese nombre.
    agi('STREAM FILE %s ""' % base)
    for sobra in (base + ".sln",):
        try:
            os.unlink(sobra)
        except OSError:
            pass


# ── oir ─────────────────────────────────────────────────────────────────────
def oir(segundos=8, idioma="es"):
    base = os.path.join(tempfile.gettempdir(), "u-" + uuid.uuid4().hex[:12])
    # RECORD FILE: fichero sin extension, formato, tecla de corte, milisegundos,
    # offset, BEEP, y los segundos de silencio que dan por terminada la frase.
    # Los 2 s de silencio son lo que hace que el que llama no tenga que pulsar
    # nada para terminar.
    agi('RECORD FILE %s wav "#" %d 0 BEEP s=2' % (base, segundos * 1000))
    fichero = base + ".wav"
    if not os.path.exists(fichero) or os.path.getsize(fichero) < 2000:
        # ⚠ Silencio. Un Whisper al que se le da silencio NO devuelve cadena
        # vacia: se inventa una frase -"Gracias por ver el video", subtitulos de
        # alguien- porque eso es lo que habia en su entrenamiento. Cortar aqui
        # por tamaño evita pagar por una alucinacion y actuar sobre ella.
        verbose("uttera: no se ha grabado nada audible")
        agi('SET VARIABLE UTTERA_TEXTO ""')
        return

    limite = b"----uttera" + uuid.uuid4().hex.encode()
    partes = []
    for campo, valor in (("model", b"whisper-1"), ("language", idioma.encode()),
                         ("response_format", b"text")):
        partes += [b"--" + limite,
                   b'Content-Disposition: form-data; name="%s"' % campo.encode(),
                   b"", valor]
    with open(fichero, "rb") as f:
        audio = f.read()
    partes += [b"--" + limite,
               b'Content-Disposition: form-data; name="file"; filename="a.wav"',
               b"Content-Type: audio/wav", b"", audio, b"--" + limite + b"--", b""]
    cuerpo = b"\r\n".join(partes)
    texto, _ = peticion("/v1/audio/transcriptions", cuerpo,
                        {"Content-Type": "multipart/form-data; boundary=" + limite.decode()})
    os.unlink(fichero)

    dicho = texto.decode("utf-8", "replace").strip()
    verbose("uttera oyo: " + dicho[:120])
    # ⚠ Las comillas del SET VARIABLE: sin ellas, un texto con espacios llega
    # partido y la variable se queda con la primera palabra.
    agi('SET VARIABLE UTTERA_TEXTO "%s"' % dicho.replace('"', "'"))


# ── entrada ─────────────────────────────────────────────────────────────────
def main():
    leer_entorno()          # hay que consumirlo aunque no se use
    if not CLAVE:
        verbose("uttera: falta UTTERA_API_KEY")
        sys.exit(1)
    quien = os.path.basename(sys.argv[0])
    args = sys.argv[1:]
    try:
        if "oir" in quien:
            oir(int(args[0]) if args else 8, args[1] if len(args) > 1 else "es")
        else:
            decir(args[0] if args else "", args[1] if len(args) > 1 else "es")
    except urllib.error.HTTPError as e:
        # El motivo viene en el cuerpo. Sin esto solo se ve "HTTP Error 402" en
        # el log de Asterisk y hay que ir a adivinar.
        verbose("uttera error %s: %s" % (e.code, e.read()[:160].decode("utf-8", "replace")))
        sys.exit(1)
    except Exception as e:
        verbose("uttera fallo: %s" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
