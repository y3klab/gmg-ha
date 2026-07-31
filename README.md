# Green Mountain Grills for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![validate](https://github.com/y3klab/gmg-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/y3klab/gmg-ha/actions/workflows/validate.yml)

Control and monitor a **Green Mountain Grills** Wi-Fi pellet grill from Home Assistant, over
your own network. No cloud account, no vendor API, no internet.

Protocol handling lives in [**gmg-local**](https://pypi.org/project/gmg-local/), a standalone
library; this repository is the Home Assistant half.

## Why you might want this

The widely-installed GMG integrations read grill temperature from a **single byte**. Anything
above 255 wraps, so a **350 °F grill reports as 94 °F** - the one number the device exists to
tell you. That is fixed here, and it is not the only thing:

- **Correct temperatures.** 16-bit little-endian, verified against a real grill.
- **Survives short packets.** The grill occasionally answers with a truncated datagram. Parsing
  one either raises or invents fields; this retries instead. Before that fix, a single stray
  packet took every entity offline.
- **One conversation at a time.** The grill serves a single client, so concurrent polls lose
  messages. All I/O is serialised, and one shared coordinator polls once per cycle for every
  entity rather than each entity polling for itself.
- **Adaptive cadence.** ~10s while cooking, ~60s while off.
- **Probes report `unknown` when unplugged** rather than a bogus 607 °F sentinel.

## Entities

13 in total, for a grill with two probes:

| domain | entities |
|---|---|
| `climate` | grill, probe 1, probe 2 |
| `sensor` | grill / probe 1 / probe 2 temperature, fire state, warning, power state, fire state progress, API version |
| `binary_sensor` | probe 1 connection, probe 2 connection |

## Install

**HACS** (custom repository): HACS → Integrations → ⋮ → Custom repositories → add
`https://github.com/y3klab/gmg-ha` as an **Integration** → install → restart Home Assistant.

**Manual:** copy `custom_components/gmg/` into your `config/custom_components/` and restart.

Then **Settings → Devices & Services → Add Integration → Green Mountain Grills**. It discovers by
UDP broadcast; if the grill is on a different VLAN, supply its IP and it will be probed directly.

Requires Home Assistant **2026.5+**. The `gmg-local` dependency is installed automatically, so
Home Assistant needs to reach PyPI on first start after installing or upgrading.

## Fire state progress

The `fire state progress` sensor exposes byte 33 of the status frame - what GMG's own cloud API
calls `fireStateProgress`. It steps in four 25% increments through whatever state the grill is
in: up through Startup, hitting 100 at the exact moment the grill switches to Running, then back
down through Cool Down to 0 as the fan stops.

**What each step physically means is not known**, and is deliberately not guessed at. Other
implementations label this byte as a pellet-hopper level; it is not - a hopper does not fill
during ignition and empty when the fan stops.

## Known hardware quirks

- **Probe targets are silently discarded while the grill is off.** Write 203, read back 0, no
  error. The integration blocks the write rather than showing a target the grill never took.
- **The spec plate rates 150-550 °F; this exposes 150-500.** Which side owns the ceiling - the
  integration's bounds or the grill's own API - is unverified, and a limit the firmware enforces
  is not ours to raise.

## Credits

**All the credit for getting these grills into Home Assistant belongs to
[@jwhitby91](https://github.com/jwhitby91)** - his integration is what put our Green Mountain
Grills into Home Assistant in the first place. 🙏

That repo has been inactive since January 2023. A Home Assistant compatibility fix was
[offered back to it](https://github.com/jwhitby91/gmg_home_assistant/pull/11) and is still open;
this carries the work forward instead - substantially rewritten since, with the protocol
extracted to `gmg-local`, but it started there.

Protocol reference cross-checked against
[`brandenc40/green-mountain-grill`](https://github.com/brandenc40/green-mountain-grill) (Go) and
`gmg` on PyPI by **Christopher McKay**.

Not affiliated with or endorsed by Green Mountain Grills.

## Licence

MIT - see [LICENSE](LICENSE).
