// The demo's positive lateral direction is to the robot's right (-Y in G1 coordinates).
const MAX_POSE_ANGLE = Math.atan2(0.8, 2.5) * 180 / Math.PI;

// Illustrative exposure: four accurate fitted steps extinguish the selected fire.
// Recompute from the prefix so replay, scrubbing and target changes are deterministic.
export function fireIntensity(steps, target, index) {
  let hits = 0;
  for (let i = 1; i <= Math.min(index, steps.length - 1); i++) {
    const step = steps[i];
    if (Math.abs(step.slope * target.lateral + step.intercept - target.expected) <= 3) hits++;
  }
  return Math.max(0, 1 - hits / 4);
}

export function poseBlend(angle) {
  const value = Number.isFinite(angle) ? angle : 0;
  return { side: value < 0 ? 'left' : 'right', weight: Math.min(1, Math.abs(value) / MAX_POSE_ANGLE) };
}

export function modelEndpoint(origin, target, prediction, teacher) {
  const radians = -(prediction - teacher) * Math.PI / 180;
  const dx = target[0] - origin[0], dy = target[1] - origin[1];
  return [origin[0] + dx * Math.cos(radians) - dy * Math.sin(radians),
    origin[1] + dx * Math.sin(radians) + dy * Math.cos(radians), target[2]];
}

// Decorative droplets follow the same aim ray; they are not a fluid simulation.
export function sprayPoint(origin, endpoint, index, count, phase) {
  const t = ((index / count + phase) % 1 + 1) % 1;
  const dx = endpoint[0] - origin[0], dy = endpoint[1] - origin[1];
  const length = Math.hypot(dx, dy) || 1;
  const spread = 0.075 * t, angle = index * 2.3999632297;
  return [origin[0] + dx * t - dy / length * Math.cos(angle) * spread,
    origin[1] + dy * t + dx / length * Math.cos(angle) * spread,
    origin[2] + (endpoint[2] - origin[2]) * t + Math.sin(angle) * spread];
}
