# Browser Training demo contracts

`runTraining` accepts an integer example count from 8 through 128 and an integer seed from 0 through 2147483647. It generates distinct synthetic teaching positions away from the fixed test positions, fits a linear model using least squares, and returns the fitted coefficients and per-case and mean absolute angular errors for both the learned prediction and the fixed forward baseline. Invalid settings fail explicitly.

The form runs the model locally and shows the computed results; its text distinguishes the exercise from incident analysis, MuJoCo and robot control. The workbench opens Training in a new tab to retain any in-memory run state. No backend API, persistence, secrets, or network inference are involved.

Changes to the teaching or model strategy should preserve or deliberately version this result contract. Verify deterministic results, input bounds, disjoint held-out positions, keyboard navigation, and the existing workbench stages.

The result additionally exposes the generated examples and one fitted coefficient pair for every prefix, including a zero-example forward baseline. The last pair must match the final model. The browser G1 visual interpolates three authored poses in response to each predicted synthetic angle; guide rays illustrate the difference from the teacher, without claiming physical nozzle alignment. Playback can be paused and scrubbed; reduced-motion users see the final state without automatic replay. A 2D fallback is retained if WebGL or assets fail. This is an illustration, not a physics simulation or a recorded robot trajectory.

Three targets display procedural flame shapes, and a bounded spray follows the illustrative aim endpoint. Each fitted step within 3° of the teacher reduces the active visual fire by one quarter; four accurate steps put it out, stop the spray, lower the G1 to its authored rest pose and show a short fading smoke effect. After a brief pause, an authored leg cycle illustrates walking to the next target before the arm rises; the chosen first fire determines the cyclic order. The fire sequence is computed from the replay prefix, so scrubbing and target changes are deterministic, and a short replay may end before all fires are out. Walking and suppression are illustrative, not physical simulations. Flame and droplet motion runs only during visible, active playback; paused, hidden and reduced-motion states remain static. The 2D fallback and metrics continue to work independently.

Walking uses two precomputed distance-matched kinematic clips, with grounded support feet and swing-foot lift, and turns while stationary before traveling. The browser interpolates poses with the same progress used for root travel, with no runtime inverse kinematics or additional backend service.

The unladen left arm counter-swings with the left leg, returning to its rest pose at the ends of the walk. The right arm and extinguisher retain their carrying pose. Arm poses share the existing walking progress and respect the same pause, scrub and reduced-motion behavior.

When a fire goes out and another remains, the G1 head turns toward the next target before the body turns to walk. The glance is derived from the target position and replay state; it is a display-only head rotation, not robot perception.

On reaching the next target the G1 raises its arm and holds an aiming pose for a replay step with spray off; only the following step can spray and reduce that fire. This state is deterministic when scrubbing and static with reduced motion.

When all three fires are out, the G1 turns and walks back to the position at the start of the replay, using the same distance-matched gait. The timeline may extend with visual-only steps if the return has not finished by the last example; example counts and learned results never exceed the actual training data. No return occurs unless all fires are out.
