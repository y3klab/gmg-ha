# Green Mountain Grills for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![validate](https://github.com/y3klab/gmg-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/y3klab/gmg-ha/actions/workflows/validate.yml)

Control and monitor a **Green Mountain Grills** Wi-Fi pellet grill from Home Assistant, over
your own network. No cloud account, no vendor API, no internet needed after setup - just delicious data.

The code that talks to the grill over the network lives in
[**gmg-local**](https://pypi.org/project/gmg-local/), a standalone library; this repository
is the Home Assistant integration.

## Features

- **Full climate control from Home Assistant.** The pit and both probes are climate
  entities - set the pit temperature and probe done-targets from any dashboard or
  automation. Every change is read back and verified, so the dial only ever shows a
  target the grill actually accepted.
- **The whole cook, on the record.** Temperatures, fire state, ignition progress,
  warnings, and power state land in the recorder every
  10 seconds while the grill is on - every cook becomes a chart in your Home Assistant
  history.
- **Automate the smoke.** Everything is an entity: text yourself when the ribs hit
  195 °F, when the fire state turns Running, or when the grill raises a warning.
- **Watch ignition happen.** The fire state progress sensor tracks the grill
  establishing its fire in real time - the whole sequence is documented in
  [The 0-1-2-3 startup cycle](docs/startup-cycle.md).
- **Local and self-sufficient.** Discovered by UDP broadcast on your LAN (or direct IP
  across VLANs). No account to create; works when the internet doesn't.

## Engineering

- **Accurate temperatures:** the grill sends each temperature as two bytes; reading only
  one wraps every reading above 255 - a 350 °F pit reads as 94 °F. Both bytes are
  read, verified against a real grill.
- **Request coalescing:** the grill answers one client at a time, so the twelve
  entities never poll it separately - every update coalesces into one shared request
  per cycle.
- **Strict parsing:** a status reply parses whole or not at all. A healthy reply is
  52 bytes; anything shorter is retried, never parsed - so no field is ever invented.
- **Read-back verification:** every change is read back from the grill and compared -
  the dial never shows a number the grill didn't actually accept.
- **Adaptive polling:** about every 10 seconds while the grill is on, every 60 while
  it's off - responsive during a cook, quiet overnight.
- **No sentinel values:** an unplugged probe reads `unknown`, not 607 °F - the
  grill's in-band placeholder for "nothing connected."

## Requirements

- A **Green Mountain Grills Wi-Fi pellet grill** on your network - one per Home
  Assistant, as the integration is single-instance. Developed against a Jim Bowie model;
  the protocol references credited below cover GMG's other Wi-Fi models.
- **Home Assistant 2026.5+.**
- **UDP port 8080** allowed between Home Assistant and the grill - the port the grill
  listens on. Only a concern across VLANs or firewalls; on a typical home network with no
  VLANs there is nothing to configure.
- **PyPI reachable on first start** after installing or upgrading - the
  [`gmg-local`](https://pypi.org/project/gmg-local/) dependency installs automatically.

## Install

Two ways - pick **one**:

- **HACS** (custom repository): HACS → Integrations → ⋮ → Custom repositories → add
  `https://github.com/y3klab/gmg-ha` as an **Integration** → install → restart Home Assistant.
- **Manual:** copy `custom_components/gmg/` into your `config/custom_components/` and restart.

Don't do both: Home Assistant loads the hand-placed copy instead of the HACS one, and
HACS updates stop taking effect.

Then **Settings → Devices & Services → Add Integration → Green Mountain Grills**. It discovers by
UDP broadcast; if the grill is on a different VLAN, supply its IP address and the integration
will contact it directly.

## Entities

12 for a grill with two probes, all served by one shared poller:

| entity | type | what it holds |
|---|---|---|
| **Grill** | `climate` | the pit: current temperature and its target |
| **Probe 1** / **Probe 2** | `climate` | the meat probes: current temperature and a done-target |
| **Temperature** | `sensor` | pit temperature on its own, for easy graphing |
| **Probe 1 temperature** / **Probe 2 temperature** | `sensor` | probe readings; `unknown` when unplugged |
| **Fire state** | `sensor` | Off / Startup / Running / Cool Down / Fail |
| **Fire state progress** | `sensor` | how established the fire is: 0 → 100 in 25% steps as it lights, reaching 100 when the pit reaches 150 °F - the moment the fire state turns Running - then descending through Cool Down. Not the 0-1-2-3 count the grill's panel shows during startup, and not a pellet level |
| **Power state** | `sensor` | Off / On / Fan (Fan is the cool-down blower) |
| **Warning** | `sensor` | the grill's own warning report |
| **Probe 1 connection** / **Probe 2 connection** | `binary_sensor` | whether a probe is physically plugged in |

## Credits

**Inspired by [@jwhitby91](https://github.com/jwhitby91)'s
[`gmg_home_assistant`](https://github.com/jwhitby91/gmg_home_assistant) integration**,
which powered my GMG+HA dashboard for years. 🙏 This integration is a from-scratch
rewrite, with the protocol in [`gmg-local`](https://pypi.org/project/gmg-local/).

Protocol reference cross-checked against
[`brandenco/green-mountain-grill`](https://github.com/brandenco/green-mountain-grill) (Go) and
`gmg` on PyPI by **Christopher McKay**.

Thanks also to the **GMG Support team**, who took the time to answer one owner's
unusually detailed questions about what the grill is doing and when.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/jop0-grill-code-dark.svg">
  <img alt="JoPº GRILL+CODE" src="docs/jop0-grill-code.svg" width="170">
</picture>

Cooked up by the **JoPº GRILL+CODE** team. The JoPº logo is original artwork and is
not covered by this repository's MIT license.

## License

MIT - see [LICENSE](LICENSE).

*Not affiliated with or endorsed by Green Mountain Grills.*
