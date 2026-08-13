# Green Mountain Grills for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![validate](https://github.com/y3klab/gmg-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/y3klab/gmg-ha/actions/workflows/validate.yml)

Control and monitor a **Green Mountain Grills** Wi-Fi pellet grill from Home Assistant, over
your own network. No cloud account, no vendor API, no internet - just delicious data.

The code that talks to the grill over the network lives in
[**gmg-local**](https://pypi.org/project/gmg-local/), a standalone library; this repository
is the Home Assistant integration.

## Who this is for

This integration lives at the intersection of three circles: cooking on a Green Mountain
Grill, running Home Assistant, and wanting to watch the numbers while the meat smokes.
That is a small, specific crew - and if you are in it, welcome. This was built for you.

What matters to that crew is what this aims at: delicious BBQ, beautiful Home Assistant
dashboards, and the tasty stream of data connecting them.

## Key features

A pellet cook runs for hours, so the engineering's one job is to never need your
attention while it runs:

- **Full climate control from Home Assistant.** The pit and both probes are climate
  entities - set the pit temperature and probe done-targets from any dashboard or
  automation. Every write is read back and verified, so the dial only ever shows a
  target the grill actually accepted.
- **The whole cook, on the record.** Temperatures, fire state, ignition progress,
  warnings, and power state land in the recorder at the 10-second cook-time cadence -
  every cook becomes a chart you can scroll years later.
- **Automate the smoke.** Everything is a first-class entity: text yourself when the
  ribs hit 195 °F, when the fire proves, or when the grill raises a warning.
- **Watch ignition happen.** The fire state progress sensor tracks the grill
  establishing its fire in real time - the startup-cycle table below was documented
  with it.
- **Local and self-sufficient.** Discovered by UDP broadcast on your LAN (or direct IP
  across VLANs). No account to create; works when the internet doesn't.
- **Engineered for the long haul.** Correct 16-bit temperatures (a 350 °F pit shows
  350 °F), one conversation at a time through a single shared poller, retries on
  truncated packets, adaptive polling (10 s cooking, 60 s off), and unplugged probes
  that read `unknown` rather than a fake 607 °F.

## Entities

13 in total, for a grill with two probes:

| domain | entities |
|---|---|
| `climate` | grill, probe 1, probe 2 |
| `sensor` | grill / probe 1 / probe 2 temperature, fire state, warning, power state, fire state progress |
| `binary_sensor` | probe 1 connection, probe 2 connection |

## Install

**HACS** (custom repository): HACS → Integrations → ⋮ → Custom repositories → add
`https://github.com/y3klab/gmg-ha` as an **Integration** → install → restart Home Assistant.

**Manual:** copy `custom_components/gmg/` into your `config/custom_components/` and restart.

Then **Settings → Devices & Services → Add Integration → Green Mountain Grills**. It discovers by
UDP broadcast; if the grill is on a different VLAN, supply its IP address and the integration
will contact it directly.

Requires Home Assistant **2026.5+**. The `gmg-local` dependency is installed automatically, so
Home Assistant needs to reach PyPI on first start after installing or upgrading.

## The 0-1-2-3 startup cycle

When the grill lights, its panel counts 0-1-2-3 through a fixed-timer ignition sequence,
then becomes the temperature readout while the fire becomes fully established:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/startup-cycle-dark.svg">
  <img alt="The 0-1-2-3 startup cycle: which hardware each panel stage runs, for how long, and the climb to 150 °F where the fire state changes to Running" src="docs/startup-cycle-light.svg">
</picture>

<details>
<summary>Plain-text version</summary>

```text
┌─────────┬───────────────┬──────────────┬─────────────────────────────────────────┐
│ display │ hardware      │ time         │ function                                │
├─────────┼───────────────┼──────────────┼─────────────────────────────────────────┤
│    0    │ auger         │ 45-60 s      │ load the firebox with pellets           │
│    1    │ igniter       │ 90 s         │ heat the pellets                        │
│    2    │ fan + igniter │ 30 s         │ fan the pellets into flame              │
│    3    │ fan + igniter │ 30 s         │ establish proof of fire: a 5 °F rise    │
│  temp   │ fan + igniter │ until +5 °F  │ still proving the fire                  │
│  temp   │ fan + auger   │ until 150 °F │ igniter off; the auger feeds the fire   │
└─────────┴───────────────┴──────────────┴─────────────────────────────────────────┘
  at 150 °F the fire state flips to RUNNING - normal temperature control begins
```

</details>

Stage-0 auger time varies by model and ambient temperature. Rows 0-3 are from
[GMG's operating manuals](https://greenmountaingrills.com/manuals/), redrawn; the `temp`
rows and the 150 °F ending are this project's own measurements. Stage 3's 30 seconds is
how long the *display* shows a 3 - the proof-of-fire wait itself continues under the
temperature readout (about 10 minutes on a measured cold start), and a pit that never
rises 5 °F within 20 minutes shows `FAL` instead. The fire state changes to Running when
the pit reaches **150 °F**, no matter what target temperature is set.

## Fire state progress

The grill reports a fire state - Startup, Running, Cool Down - and a progress value beside
it. The `fire state progress` sensor exposes that value, byte 33 of the grill's status reply -
what GMG's own cloud API calls `fireStateProgress`. It steps in four 25% increments through
whatever state the grill is in: up through Startup, hitting 100 at the exact moment the grill
switches to Running (150 °F, see above), then back down through Cool Down to 0 as the fan
stops.

**It is not the panel's 0-1-2-3 cycle.** On a measured cold start the panel finished its
count while this sensor sat at 50; the value kept climbing for another 15 minutes while the
fire established. No one has established what each 25% step physically measures, so the
steps are deliberately left unlabeled. Other
implementations label this byte as a pellet-hopper level; it is not - a hopper does not fill
during ignition and empty when the fan stops.

## Known hardware quirks

- **Probe targets are silently discarded while the grill is off.** Set a probe target of
  203 °F while the grill is off: it reads back as 0, with no error. The integration blocks
  the write rather than showing a target the grill never accepted.
- **The label on the grill rates 150-550 °F; this integration exposes 150-500.** Whether that
  ceiling comes from this integration's bounds or from the grill's own API is unverified, and
  this integration does not raise a limit the grill's firmware may enforce.

## Credits

**All the credit for getting these grills into Home Assistant belongs to
[@jwhitby91](https://github.com/jwhitby91)** - his integration is what put our Green Mountain
Grills into Home Assistant in the first place. 🙏

That repo has been inactive since January 2023. A Home Assistant compatibility fix was
[offered back to it](https://github.com/jwhitby91/gmg_home_assistant/pull/11) and is still open;
this project continues the work instead - substantially rewritten since, with the protocol
code extracted to `gmg-local`, but it started there.

Protocol reference cross-checked against
[`brandenc40/green-mountain-grill`](https://github.com/brandenc40/green-mountain-grill) (Go) and
`gmg` on PyPI by **Christopher McKay**.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/jop0-grill-code-dark.svg">
  <img alt="JoPº GRILL+CODE" src="docs/jop0-grill-code.svg" width="170">
</picture>

Cooked up by the **JoP⁰ GRILL+CODE** team. The JoPº logo is original artwork and is
not covered by this repository's MIT license.

Not affiliated with or endorsed by Green Mountain Grills.

## License

MIT - see [LICENSE](LICENSE).
