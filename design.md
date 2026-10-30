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

After the return, a compact success badge confirms the demo is complete. Its brief entrance and checkmark animation run only on an automatic replay reaching that state; scrubbing directly to it and reduced-motion mode show the same message without animation. Leaving the completed state hides the badge so replay can trigger it again.

## Shared dropdown and workspace menu contract

Visual and interaction reference: [ReUI basic dropdown menu (`@reui/c-dropdown-menu-1`)](https://reui.io/components/dropdown-menu). Use its button trigger, anchored menu surface, compact options, selected indication, and workspace-switcher treatment. The production app is static HTML/CSS/ES modules, so implement this contract in `static/dropdown-menu.mjs` and `static/dropdown-menu.css`; do not add React, Tailwind, or a second build system solely to run the Shadcn CLI.

`upgradeSelects(root)` enhances each `select[data-dropdown-menu]` once. The native `<select>` remains the source of truth and stays in the DOM for existing consumers; the enhanced button mirrors its label, selected option, and disabled state. Changing a menu option sets the native value and dispatches a bubbling `change` event, preserving the current Workbench and Training event handlers. `MutationObserver` refreshes option lists and selected/disabled attributes when Workbench options are replaced or changed. With JavaScript unavailable, the original native select remains usable. Supported variation is limited to accessible label, fixed or dynamically replaced option lists, and disabled state; consumers must not add a parallel selected-value store.

`upgradeWorkspaceMenus(root)` wires the static Workbench and Training links into the same visual menu pattern. Links remain real navigation targets, preserve the Workbench's new-tab behavior for Training, and expose the active page with `aria-current="page"`. They do not call training or simulation logic.

The trigger exposes `aria-haspopup`, `aria-expanded`, and `aria-controls`. Pointer, Enter, and Space open the menu with focus on the first option; ArrowDown/ArrowUp open at the first/last option, and arrows move among choices. Home/End move to the ends. Escape closes and restores trigger focus; outside pointer/focus closes; choosing a value updates the select, closes the menu, and restores focus. Visible labels focus/open the enhanced select. Reduced-motion disables menu transitions. Every select and workspace menu uses the shared trigger, surface, hover/focus, selected, disabled, and responsive styles.

| Component | Responsibility and expected variation | Extension mechanism | Protected core / verification | OCP review |
| --- | --- | --- | --- | --- |
| Shared select menu | Render one accessible menu for a marked native select; labels, option lists, and disabled state vary | Idempotent `upgradeSelects(root)` registration; native select and its bubbling `change` event remain the stable contract | Training/workbench algorithms and event handlers unchanged; `frontend_evidence_check.cjs`, `frontend_operations_check.cjs`, `test_training_demo.mjs`, and browser interaction checks | Pass |
| Workspace menu | Present existing route links with current-page indication; route set is supplied by each page | Idempotent `upgradeWorkspaceMenus(root)` enhancement of authored links | URLs and new-tab behavior remain on anchors; frontend navigation evidence and desktop/mobile layout checks | Pass |
