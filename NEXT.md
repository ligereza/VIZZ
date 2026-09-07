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
triangulated eyes to a screen fraction. That composition is not a test. If a
regression ever breaks the seam between two of those stages, the current unit
tests would each still pass.

`requirements.txt` pins only NumPy. Nothing here needs more, which is the
point: the GPU tracker, camera drivers, permissions and UI are separate layers,
and this repository should stay the part that runs without any of them.
