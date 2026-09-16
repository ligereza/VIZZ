# VIZZ

VIZZ is the eye-tracking and visual-geometry engine for FARMAKSIA. Its core
turns observations from two cameras into geometric quantities that can be
audited: rays, 3-D points, depth, inter-eye distance, and screen-plane
intersections.

## Important boundary

The geometry layer does not claim that an infrared image is a depth camera.
Metric stereo requires a calibrated rig: intrinsics for both cameras and the
relative rotation and translation between them. Without that calibration the
correct state is `CALIBRATION_REQUIRED`, not a guessed distance.
`calibration_state` answers that as a state so a caller can ask before
showing a distance; the metric functions themselves refuse rather than guess.
`calibration_audit` adds the second boundary: valid caller-supplied model
parameters are not physical calibration evidence, so it reports
`CALIBRATION_EVIDENCE_REQUIRED` and keeps `metric_depth_authorized=false`.
Its `evidence_scope` must be declared explicitly (`synthetic_only` requires a
`provenance_ref`; otherwise the default is `physical_calibration_required`).
The existing `calibration_state` and `binocular_measurement` outputs also carry
`calibration_audit_required=true` and never authorize metric depth on their own.

`screen_plane_intersection` reports where a ray meets one flat screen, as a
world point and as a fraction of each screen edge. A curved display, or
several monitors at different angles, is not this: each needs its own model
rather than a plane fitted to it silently. The distance along the ray is
reported and not constrained, because a minimum viewing distance belongs to a
physical setup and not to this scale-free geometry.

Triangulation also reports the ray-pair condition number. Callers may pass
`max_condition_number` to refuse a geometrically unstable result instead of
displaying a depth whose error is dominated by nearly parallel rays.

The tracker, GPU models, camera drivers, permissions, and UI are separate
layers. This repository contains the lightweight CPU geometry kernel only;
GPU inference can feed it observations without coupling the kernel to a
particular webcam, Hikvision model, operating system, or credential.

## Run

```text
python -m unittest discover -s tests -v
```

The bounded synthetic characterization can be regenerated with:

```text
python experiments/characterize_noise.py
```

It reports pixel sensitivity and baseline conditioning only; it does not
claim real-camera calibration.

Calibration sensitivity can be regenerated separately with:

```text
python experiments/characterize_calibration.py
```

That report perturbs focal length and camera pose in a synthetic rig and keeps
the resulting point error explicit.

The model/evidence boundary can be regenerated with:

```text
python experiments/audit_model_calibration.py
```

It records that a numerically valid synthetic model still has no physical
calibration evidence and therefore cannot authorize metric depth.

A seeded distribution combining pixel noise and calibration perturbations can
be regenerated with:

```text
python experiments/characterize_distribution.py
```

Its median and p95 are fixture statistics, not production tolerances.

The local capture surface can be inspected without reading frames with:

```text
python experiments/probe_capture_surface.py
```

Device presence does not satisfy calibration; the probe remains
`CALIBRATION_REQUIRED` and records that no frames were captured.

The tests use synthetic cameras and points. They do not open a camera, store
frames, contact a network, or make an ophthalmological claim.

The synthetic experiments share their camera, intrinsics, rotation and
projection fixture in experiments/synthetic_rig.py; the individual scripts
keep only the measurement or sampling question they are meant to answer.
