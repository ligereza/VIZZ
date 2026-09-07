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

`screen_plane_intersection` reports where a ray meets one flat screen, as a
world point and as a fraction of each screen edge. A curved display, or
several monitors at different angles, is not this: each needs its own model
rather than a plane fitted to it silently. The distance along the ray is
reported and not constrained, because a minimum viewing distance belongs to a
physical setup and not to this scale-free geometry.

The tracker, GPU models, camera drivers, permissions, and UI are separate
layers. This repository contains the lightweight CPU geometry kernel only;
GPU inference can feed it observations without coupling the kernel to a
particular webcam, Hikvision model, operating system, or credential.

## Run

```text
python -m unittest discover -s tests -v
```

The tests use synthetic cameras and points. They do not open a camera, store
frames, contact a network, or make an ophthalmological claim.
