# CLAUDE.md

## What this is

A Home Assistant custom integration for Green Mountain Grills Wi-Fi pellet grills, installed
via HACS as a custom repository. Domain **`gmg`**.

Protocol handling is **not here**. It lives in
[`gmg-local`](https://pypi.org/project/gmg-local/), version-pinned in
`manifest.json` under `"requirements"`.

## Structure

```
custom_components/gmg/
  __init__.py       setup, one shared coordinator per grill, entity migrations
  coordinator.py    DataUpdateCoordinator, adaptive poll interval
  climate.py        grill + 2 probes
  sensor.py         7 sensors      binary_sensor.py  2 probe-connectivity sensors
  config_flow.py    UI setup, YAML import
  const.py  manifest.json  strings.json  translations/  brand/
```

12 entities for a two-probe grill: 3 climate, 7 sensor, 2 binary_sensor. The
firmware string lives on the device (``sw_version``), not in an entity.

## Conventions

- **One coordinator per grill, shared by every entity.** The grill answers a single client
  at a time, so per-entity polling contends and knocks entities offline. Entities are
  `CoordinatorEntity` and never poll.
- **`brand/` holds the icons.** Since HA 2026.3, a custom integration ships its own brand
  images locally and they take priority over the CDN. **Do not submit them to
  `home-assistant/brands`** - that repo's `custom_integrations` folder is legacy and
  auto-closes such PRs.
- **Version lives in `manifest.json`** and must match the release tag.
- `climate.py` uses `_attr_*` declarations over property methods where HA supports it.

## Gotchas

- **Renaming an entity is not a string change.** `unique_id` is
  `"<serial>_<key_suffix>"`; changing the suffix orphans the entity and starts a fresh one
  with **no recorder history**. `__init__.py` carries `_RENAMED_ENTITIES` and a migration
  that runs before platforms load. It is idempotent and only touches an `entity_id` that is
  still the generated one, so a user's own rename is never clobbered. **Any future rename
  needs an entry there.**
- **HA must reach PyPI on first start** after install or upgrade, to fetch `gmg-local`.
  Without it the integration fails to set up - the most likely failure mode after a version
  bump.
- **Never hand-place a copy in `config/custom_components/` alongside the HACS install.**
  They collide and the hand-placed one wins on load order.
- **Probe writes are silently discarded while the grill is off.** Write 203, read back 0, no
  error. The integration refuses the write rather than showing a target the grill never
  took, and verifies the read-back afterwards.
- **The spec plate rates 150-550 °F; this exposes 150-500.** Whether the ceiling is ours or
  the grill's API is unverified. A limit the firmware enforces is not ours to raise.
- **`no usable status from grill ... after 5 tries` is a grill-side fault, ~1 per 3.7 h.**
  Diagnosed 2026-07-30, not caused by anything here. Onset is Poisson (no periodicity at any
  period 10 min - 24 h), so nothing scheduled is contending; and independent packet loss is
  refuted by arithmetic, since all 5 retries failing would need a 34% loss rate. 30 of 32
  events carry an identical `(4 silent, 1 too short: [1])` signature - **a one-byte datagram**,
  which must have been generated that way because a corrupted frame never reaches a socket.
  Episodes last ~6.4 s, measured twice to within 21 ms. **Don't read a recurrence as a
  regression, and don't read a short clean window as a fix** - at 1 per 3.7 h a 30-minute
  sample proves nothing. Full analysis and the packet-capture test that would identify the
  emitting device are in the private notes.
- **`/api/config` `state` does not prove a restart happened.** It can return `RUNNING`
  seconds into a restart that hasn't begun. Gate on a log line timestamped after the
  command.

## Releasing

```
bump manifest.json version → commit → tag vX.Y.Z → push tag → create a GitHub Release
```

Release notes are **informative, succinct, friendly**: the tagline names what
changed in plain words; the body opens by naming the thing, states facts
declaratively with real commands and numbers, names any manual step plainly
without softening it, and cuts process trivia (test counts, internal
mechanics). Always state upgrade impact.

`validate.yml` runs **hassfest** (HA's own manifest/structure check) and the **HACS action**
on every push and weekly. Both must pass; the weekly run is there to catch breakage from
Home Assistant releases rather than from our own commits.

## Don't

- **Don't re-add protocol code here.** Home Assistant's rule is that core carries none. A
  wire-format bug is fixed in `gmg-local` and picked up by a version bump.
- **Don't change the `gmg` domain.** It is permanent in practice - every entity_id and
  config entry depends on it.
- **Don't rename an entity without a migration entry.**
- **Don't add HA-specific behavior to `gmg-local`** to make something here easier. That
  library is deliberately usable without Home Assistant.

## Credits

See the README. Inspired by `jwhitby91/gmg_home_assistant`; rewritten from scratch (the
rewrite was measured - 8 non-trivial verbatim lines remained, all one-way-to-write-it
socket boilerplate; see the private provenance note). The old fork is **archived rather
than deleted**, because an open upstream PR still lives on one of its branches - deleting
it would close that PR and destroy the diff.
