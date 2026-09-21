# Changelog — uttera-examples

Componente interno. Formato inspirado en Keep a Changelog.

## [Sin publicar] — 2026-09-22

### Changed
- 🔴 **Los cuatro guiones de la skill, con nombre en inglés**, antes de
  publicarla en ClawHub:

  | antes | ahora |
  |---|---|
  | `transcribir.sh` | `transcribe.sh` |
  | `resumir.sh` | `summarize.sh` |
  | `traducir.sh` | `translate.sh` |
  | `decir.sh` | `speak.sh` |

  - **Por qué ahora**: es la regla de siempre —código y nombres de fichero en
    inglés—, pero aquí pesa el doble: van dentro de un `SKILL.md` escrito en
    inglés, los ejecutan agentes de todo el mundo, y **una vez publicada en
    ClawHub, renombrarlos rompe a quien ya la tenga instalada**.
  - Los **mensajes que ve quien los usa** también pasan a inglés (`file is
    missing or empty`, `usage: …`). Los comentarios se quedan en castellano,
    que es la regla.
  - Versión **1.0.0 → 1.1.0**: cambiar los nombres es romper la interfaz.

### Fixed
- ⚠ **`transcribe.sh` y `speak.sh` usaban rutas FIJAS en `/tmp`**
  (`/tmp/uttera.hdr`, `/tmp/uttera.body`). Una skill la ejecutan varios
  agentes a la vez, que es justo su razón de ser: dos a la vez se pisaban las
  cabeceras y el cuerpo de la petición. Ahora `mktemp` y `trap … EXIT`.
## [Sin publicar] — 2026-09-21

### Changed
- **El nodo de n8n: un solo cuerpo para Sonidos y Música.** Hasta hoy había
  que escribir dos, porque Música pedía `prompt`/`seconds`/`translate` y
  Sonidos los mismos datos en castellano. Ahora los dos motores piden lo
  mismo y la única diferencia es `steps`, que sólo tiene Música.

⚠ **`uttera-examples` es el ÚNICO repositorio de Uttera que se publica**, y
aquí manda GitHub: el de amon es un espejo de sólo lectura que *tira* de
aquí. Un cambio hecho en el espejo no llega solo; hay que empujarlo aquí.

