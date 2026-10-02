# Changelog — uttera-examples

Componente interno. Formato inspirado en Keep a Changelog.


## [Sin publicar] — 2026-10-02

### Added — asterisk/panel
- **Envío del PDF firmado por email** a una lista FIJA de destinatarios,
  configurable en `/settings` (desplegable en el panel; el botón solo se activa
  cuando el informe ya está generado). El backend valida el destinatario contra
  la lista —no se puede enviar a ninguna otra dirección— y exige que el PDF ya
  exista. Asunto y cuerpo configurables con marcadores `{caller} {time}
  {duration} {uid} {company}`. Envío por SMTP con autenticación opcional
  (STARTTLS, `PANEL_SMTP_*`), para pasar políticas DMARC sin depender de un
  relay basado en IP de origen.
- **Enlaces personalizados** en la barra superior del panel (p.ej. a un listado
  externo o a otra aplicación), configurables en `/settings`.
- **Usuarios de solo lectura** (`PANEL_USERS`): ven llamadas y generan/envían
  informes, pero no acceden a `/settings` (reservado al administrador).
- **Registro de auditoría** (`/var/log/uttera-panel/audit.log`, vía
  `LogsDirectory`, escribible bajo `ProtectSystem=strict`): quién, desde qué IP,
  qué acción —ver llamada, oír grabación, informe, envío por email, cambios de
  ajustes, accesos denegados, logins fallidos— y cuándo, como corresponde a un
  listado de grabaciones (datos personales).


## [Sin publicar] — 2026-09-22 (2)

### Added
- **La skill cubre ahora TODO lo que ofrece la API**, no seis cosas de diez.
  Lo pidió Hugo —*«revisa todos los servicios, que no es mi trabajo
  acordarme»*— y salió de comparar las rutas del gatekeeper contra lo que
  exponen la skill y el MCP, en vez de enumerarlas de memoria.

  | nuevo | qué hace |
  |---|---|
  | `sound.sh` | un efecto de sonido |
  | `music.sh` | una pieza de música |
  | `scene.sh` | una escena entera: la planifica, la genera y la mezcla |
  | `pronounce.sh` | puntúa cómo se pronunció una frase |
  | `voices.sh` | qué voces hay |
  | `verify.sh` | comprobar que un informe firmado es auténtico |

- ⚠ `verify.sh` **no pide clave a propósito**: verificar una firma es una
  operación de clave pública. El día que haga falta una cuenta para
  comprobarla, la firma habrá dejado de servir para lo que se hizo.

### Changed
- **Los comentarios de los guiones, también en inglés.** Los lee gente de
  fuera; el castellano se queda en `SKILL.es.md`, que es documentación para
  el cliente.
- Las **etiquetas** de `SKILL.es.md` estaban en castellano (`voz`,
  `transcripcion`…). Son metadatos que consume el catálogo, no texto para
  nadie: van en inglés como el resto de lo que viaja.
- Versión **1.3.0**.

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

