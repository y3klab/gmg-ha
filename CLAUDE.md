# CLAUDE.md

## What this is

A Home Assistant custom integration for Green Mountain Grills Wi-Fi pellet grills, installed
via HACS as a custom repository. Domain **`gmg`**.

Protocol handling is **not here**. It lives in
[`gmg-local`](https://pypi.org/project/gmg-local/), pinned in `manifest.json` as
`"requirements": ["gmg-local==0.1.0"]`.

## Structure

```
custom_components/gmg/
  __init__.py       setup, one shared coordinator per grill, entity migrations
  coordinator.py    DataUpdateCoordinator, adaptive poll interval
  climate.py        grill + 2 probes
  sensor.py         8 sensors      binary_sensor.py  2 probe-connectivity sensors
  config_flow.py    UI setup, YAML import
  const.py  manifest.json  strings.json  translations/  brand/
```

13 entities for a two-probe grill: 3 climate, 8 sensor, 2 binary_sensor.

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
- **`no usable status from grill ... after 5 tries` appears roughly hourly.** Pre-existing
  and unexplained; not caused by any recent change. Don't read a recurrence as a regression,
  and don't read a short clean window as a fix - at ~1 per 4.6 h, a 30-minute sample proves
  nothing.
- **`/api/config` `state` does not prove a restart happened.** It can return `RUNNING`
  seconds into a restart that hasn't begun. Gate on a log line timestamped after the
  command.

## Releasing

```
bump manifest.json version → commit → tag vX.Y.Z → push tag → create a GitHub Release
```

`validate.yml` runs **hassfest** (HA's own manifest/structure check) and the **HACS action**
on every push and weekly. Both must pass; the weekly run is there to catch breakage from
Home Assistant releases rather than from our own commits.

## Don't

- **Don't re-add protocol code here.** Home Assistant's rule is that core carries none. A
  wire-format bug is fixed in `gmg-local` and picked up by a version bump.
- **Don't change the `gmg` domain.** It is permanent in practice - every entity_id and
  config entry depends on it.
- **Don't rename an entity without a migration entry.**
- **Don't add HA-specific behaviour to `gmg-local`** to make something here easier. That
  library is deliberately usable without Home Assistant.

## Credits

See the README. Originally forked from `jwhitby91/gmg_home_assistant`, since substantially
rewritten. The old fork is **archived rather than deleted**, because an open upstream PR
still lives on one of its branches - deleting it would close that PR and destroy the diff.
