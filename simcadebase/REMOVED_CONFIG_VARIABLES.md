# Removed Config Variables (`simcade_vehicle_config.txt`)

Reference log of dead, redundant, or duplicate variables removed from `simcade_vehicle_config.txt` and why.

## Dead Config Keys (Unused in Codebase)

### `CONFIG.VEHICLE_CFG`
- **`InvertForward = false`** — Never read anywhere. Use `chassisForward` (e.g., `Vector(-1, 0, 0)`) to orient the chassis instead.
- **`InvertRight = false`** — Never read anywhere. Flipping `right` independently of `forward` and `up` would invert `up` or produce a left-handed frame; `chassisForward` uniquely determines `right` via `fwd:cross(up)`.
- **`AutoAlignToPod = false`** — Never read anywhere. Not implemented; if ever wanted in the future, it could derive `chassisForward` from the wired `Pod` seat's facing direction projected into `Base`-local space.

### `CONFIG.TIRE_CFG`
- **`SlipAnglePeak = 9.5`** — Never read anywhere. Peak lateral slip angle is determined by the Pacejka compound parameters (`Lat_B`, `Lat_C`, `Lat_E`).
- **`BrakeTransferFactor = 5.6`** — Never read anywhere. Dynamic braking weight transfer is handled by `WEIGHT_SHIFT_CFG` (`LongitudinalTransfer`, `FrontLongMult`, `RearLongMult`) and `SUSPENSION_CFG.pitchTransferBrakeMult`.
- **`ThrottleTransferFactor = 20.4`** — Never read anywhere. Dynamic acceleration weight transfer is handled by `WEIGHT_SHIFT_CFG` and `SUSPENSION_CFG.pitchTransferAccelMult`.
- **`Front.Radius = 11`**, **`Rear.Radius = 11`** — Never read anywhere. Wheel physics radius is configured per wheel in `CONFIG.WHEELS[i].radius`.

### `CONFIG.ENGINE_CFG`
- **`crankFuelTime = 0.15`** — Never read anywhere. Starter/cranking timing only uses `crankRPM` and `crankTime`.
- **`UseRPMBasedGear = true`** — Never read anywhere. `SimcadeGearbox.evaluateAutoShift` always uses RPM-based shifting (`ComfortUpshiftRPM`/`SportUpshiftRPM`/`ComfortDownshiftRPM`/`SportDownshiftRPM`); there is no speed-only auto-shift mode.
- **`TorqueVectoring = 0.18`** — Never read anywhere. Differential behavior is controlled by `FrontDiffType`/`RearDiffType`/`CenterDiffType` and their LSD stiffness/lock ratio settings.

### `CONFIG.REVERSE_CFG` (entire table)
- **`MaxReverseEngageKMH = 18`**, **`MaxForwardEngageKMH = 20`** — Never read anywhere (also removed unused `local REVERSE_CFG = CONFIG.REVERSE_CFG or {}` from `simcade_core.txt`). Reverse engagement speed is controlled by `ENGINE_CFG.SpeedToReverse`.

## Shadowed / Redundant Keys

### `CONFIG.CAMERA_CFG`
- **`toggleKey = KEY.V`** — Legacy fallback in `simcade_core.txt` only read when `CONTROLS_CFG.CameraToggle` is `nil`. Since `CONTROLS_CFG.CameraToggle` is set, this key had no effect.

## Duplicate Keys Cleaned Up

### `CONFIG.ENGINE_CFG`
- **`FrontDiffType`** — Defined twice consecutively; kept single entry (`0`).
- **`CenterDiffType`** — Defined twice; kept single entry (`0`).
- **`DiffLockToggleable`** — Set to `true` then overwritten with `false` two lines later; kept single entry (`false`).

## Unused Local Constants

- **`local MAT_CLIP = 73`** — Never referenced in `simcade_vehicle_config.txt`.
- *(Kept `MAT_SLOSH = 83` and `MAT_DEFAULT = 88` and replaced the hardcoded `[83]` / `[88]` table keys with them.)*

## Related Fixes Applied (Not Removed)

- **`TIRE_CFG.Front.Aspect` / `Rear.Aspect`** — Restored and wired up in `simcade_tires.txt` matching `tire_simulation_v2_core.txt` (`aspectStiff = 50 / max(10, Aspect)`, scaling `Lat_B` by `aspectStiff` and `Long_B` by `(1 + (aspectStiff - 1) * 0.5) * sqrt(max(0.5, widthFactor))`; also accepts `AspectRatio`).
- **`SOUND_CFG.TurboBOVPitch`** — Kept and wired up in `simcade_sounds.txt` (previously hardcoded to pitch `102`; now uses `clamp(102 * (SND.TurboBOVPitch or 1.0), 40, 220)`).
- **`ENGINE_CFG.FrontLSDLockRatio` / `RearLSDLockRatio`** — Fixed `simcade_vehicle_physics.txt` to accept both `0..1` fractions (like `0.75`) and legacy `0..100` percentages instead of dividing `0.75` by `100`.
