# Resume primero, y luego paga a tu LLM

*[English version](README.md)*

Si quieres que un modelo de lenguaje —Claude, GPT, Gemini, el que sea— razone sobre
lo que se dijo en una llamada, la vía cara es pasarle **la transcripción entera**.
La barata es pasarle **el resumen**.

`/v1/summarize` devuelve las dos cosas en la misma respuesta, así que eliges en
cada petición y nunca pagas dos veces.

## La cifra

Medido sobre una grabación real de 70 minutos, prosa variada, con el tokenizador
`o200k_base`:

| Lo que le mandas al LLM | Palabras | Tokens |
|---|---|---|
| Transcripción completa | 10.429 | **15.410** |
| Resumen estructurado | 294 – 422 | **484 – 673** |

**Entre 20 y 30 veces menos tokens de entrada.** El rango no es dejadez: resumir
no es determinista, y la misma grabación resumida dos veces dio 484 y 673 tokens.

El ahorro crece con la duración. La transcripción crece en línea recta con los
minutos de audio; el resumen no.

## Ejecutarlo

```bash
export UTTERA_API_KEY=sk-echo-...
./summarise-first.py reunion.mp3
./summarise-first.py reunion.mp3 --ask "¿Qué acordamos y de quién es cada cosa?"
```

Solo biblioteca estándar. Si resulta que tienes `tiktoken` instalado, las cuentas
son exactas; si no, se estiman a 4 caracteres por token y la salida lo dice.

Escribe `prompt.json` —el payload exacto que mandarías a `/v1/chat/completions` o
a `/v1/messages`— en vez de enviarlo. Así lees lo que vas a pagar antes de pagarlo,
y el ejemplo no necesita cuenta en un tercero para servir de algo.

## Cuándo esto es mala idea

**Grabaciones cortas.** En un corte de 90 segundos el mismo script da 1,2×: el
resumen es casi tan largo como la transcripción. Por debajo de unos cinco minutos,
no merece la pena.

**Preguntas que necesitan las palabras exactas.** Un resumen es una pérdida de
información *deliberada*. Si tu prompt depende de una cita literal, del momento en
que se dijo algo, o de un dato que aparece una sola vez y de pasada —un número de
pedido, un importe, un apellido—, el resumen puede no traerlo.

La regla práctica: resumen para *«¿de qué iba esto y qué hay que hacer?»*,
transcripción para *«¿qué dijo exactamente?»*.

## Algo que no va de dinero

Si al tercero solo le llega el resumen, **la grabación y la transcripción literal
no salen de aquí**. Menos superficie expuesta, y una transferencia internacional
menos que justificar en tu registro de tratamientos.

Y fíjate en lo que hace el payload que genera: mete el resumen en el turno del
usuario y avisa, en el turno de sistema, de que ese texto es **datos, no
instrucciones**. Todo lo que sale de una transcripción vino de un audio que tú no
controlas. Trátalo como tal.
