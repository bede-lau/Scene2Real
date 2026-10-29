# Browser Training demo contracts

`runTraining` accepts an integer example count from 8 through 128 and an integer seed from 0 through 2147483647. It generates distinct synthetic teaching positions away from the fixed test positions, fits a linear model using least squares, and returns the fitted coefficients and per-case and mean absolute angular errors for both the learned prediction and the fixed forward baseline. Invalid settings fail explicitly.

The form runs the model locally and shows the computed results; its text distinguishes the exercise from incident analysis, MuJoCo and robot control. The workbench opens Training in a new tab to retain any in-memory run state. No backend API, persistence, secrets, or network inference are involved.

Changes to the teaching or model strategy should preserve or deliberately version this result contract. Verify deterministic results, input bounds, disjoint held-out positions, keyboard navigation, and the existing workbench stages.
