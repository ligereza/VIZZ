# NEXT — open work, observations, suggestions

Written from memory at the end of the 2026-09-07 session, without re-reading
the tree. Re-measure any number here before acting on it. Not a contract.

## What changed and what it means

The README promised "rays, 3-D points, depth, inter-eye distance, and
screen-plane intersections" and a `CALIBRATION_REQUIRED` state. Two of those
did not exist: there was no screen model at all, and the only occurrences of
`CALIBRATION_REQUIRED` in the repository were in that sentence. They exist now,
so the README describes the kernel rather than announcing it.

## Not audited, and it is the interesting part

**The triangulation numerics beyond the tests.** The tests use synthetic
cameras with a clean 0.2 m baseline and exact correspondences. Nothing measures
conditioning as the baseline shortens, how intrinsic or pose error propagates
into the reported depth, or what residual is actually tolerable. `max_residual`
is a parameter with no derivation behind it: a caller passes a number and the
kernel refuses above it, and no test says where that number should come from.

The kernel now reports a ray-pair condition number and can refuse a caller-
supplied maximum. A deterministic test also composes pixel → ray →
triangulation → screen intersection and exercises condition/residual refusal;
another test makes the change in estimated ray depth under subpixel input
perturbations observable instead of hiding it.
The suite also confirms that shortening the baseline increases the reported ray
condition number, while the threshold remains a rig-level policy.

`experiments/characterize_noise.py` now records a bounded synthetic sweep: a
0.25 px perturbation moves the estimated point by about 0.00157 world units,
and a 1 px perturbation by about 0.00630 in the same fixture. The residual
stays near zero because the perturbation is coplanar, which is evidence that a
residual-only gate is insufficient. This is still not a real-camera noise
model. A 0.5 px vertical perturbation produces a measurable non-coplanar
residual, so the artifact records both error signatures separately.
The thresholds are still rig-level policies, not universal constants: they
need calibration and image-noise experiments before production use.

`calibration_audit` now separates a numerically valid caller-supplied model
from physical calibration evidence. A valid synthetic rig is therefore
`geometry_status=METRIC_STEREO_READY` but
`status=CALIBRATION_EVIDENCE_REQUIRED`, with metric-depth authorization and
depth publication both false. Its scope is declared by the caller and never
inferred from matrices; `synthetic_only` requires a provenance reference.
No evidence pathway is claimed by this kernel.
`experiments/audit_model_calibration.py` records that boundary as
`results/calibration-audit-v1.json`.

Legacy geometry consumers now receive `metric_depth_authorized=false` and
`calibration_audit_required=true` directly from `calibration_state` and
`binocular_measurement`, so checking only the old ready status cannot be read
as physical authorization.

`experiments/characterize_calibration.py` adds a second bounded report using
clean observations from a true rig and perturbed calibration at reconstruction:
one percent focal-length error moves the point by about 0.00678 world units,
while a 0.5° yaw error moves it by about 0.04660. These are fixture sensitivities,
not universal tolerances or real-camera estimates.

The local capability probe finds two `/dev/video*` nodes with the same
`Integrated_Webcam_HD` name, but records `CALIBRATION_REQUIRED`: node presence
does not establish two cameras, intrinsics, pose, or permission to show metric
depth. It lists formats only and captures/stores no frames.

`experiments/characterize_distribution.py` adds a seeded 100-sample sweep
combining 0.2 px pixel noise, 0.2% focal uncertainty and 0.1° yaw uncertainty.
All 100 samples remain accounted for; point-error median/p95 are 0.00545/0.01679
world units. Those values are reproducible fixture statistics, not a hardware
noise model or a production threshold.

For a kernel whose whole boundary is "refuse rather than guess a distance",
that gap matters more than the features. A rig can be calibrated, pass
`calibration_state`, and still produce a depth whose error is larger than the
quantity being measured.

## Boundaries that are deliberate, so they do not drift

`ScreenPlane` is one flat screen. A curved display, or several monitors at
different angles, needs its own model and must not arrive as a plane fitted to
it silently.

`distance_along_ray` is reported and not constrained. A minimum viewing
distance belongs to a physical setup, not to scale-free geometry, so the caller
asserts it. An origin sitting on the plane yields a near-zero distance rather
than an error, and an origin exactly on it is refused.

Distortion calibration is outside this kernel on purpose, so it cannot be
silently ignored. If it ever enters, it should enter as a declared stage and
not as an assumption that image points arrived undistorted.

## Suggestions

The kernel now composes end to end on synthetic input: pixels to rays to
triangulated eyes to a screen fraction. The composition test protects the seam
between those stages, while real-camera noise and calibration remain outside
the current evidence.

`requirements.txt` pins only NumPy. Nothing here needs more, which is the
point: the GPU tracker, camera drivers, permissions and UI are separate layers,
and this repository should stay the part that runs without any of them.
