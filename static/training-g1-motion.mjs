// The demo's positive lateral direction is to the robot's right (-Y in G1 coordinates).
const MAX_POSE_ANGLE = Math.atan2(0.8, 2.5) * 180 / Math.PI;

// Illustrative exposure: four accurate fitted steps extinguish the selected fire.
// Recompute from the prefix so replay, scrubbing and target changes are deterministic.
export function fireEffect(steps, target, index) {
  let hits = 0, extinguishedAt = null;
  for (let i = 1; i <= Math.min(index, steps.length - 1); i++) {
    const step = steps[i];
    if (Math.abs(step.slope * target.lateral + step.intercept - target.expected) <= 3 && ++hits === 4) extinguishedAt = i;
  }
  const fire = Math.max(0, 1 - hits / 4);
  const smoke = extinguishedAt === null ? 0 : Math.max(0, 1 - (Math.min(index, steps.length - 1) - extinguishedAt) / 5);
  return { fire, smoke, spraying: fire > 0 };
}

export function fireIntensity(steps, target, index) { return fireEffect(steps, target, index).fire; }

// Replay the same small deterministic sequence for every scrub position.
export function fireSequence(steps, targets, index, firstIndex) {
  const positions = [0, 4, 8];
  const first = Math.max(0, positions.indexOf(firstIndex));
  const fires = [1, 1, 1];
  let slot = first, hits = 0, completed = 0, hold = 0, extinguishedAt = -1, arrivedAt = -1;
  const end = Math.min(Math.max(0, index), steps.length - 1);
  for (let i = 1; i <= end; i++) {
    if (hold > 0) {
      hold--;
      if (hold === 0 && completed < 3) { slot = (slot + 1) % 3; hits = 0; arrivedAt = i; }
      continue;
    }
    if (completed === 3) continue;
    const target = targets[positions[slot]], step = steps[i];
    if (Math.abs(step.slope * target.lateral + step.intercept - target.expected) <= 3) {
      hits++;
      fires[slot] = Math.max(0, 1 - hits / 4);
      if (hits === 4) { completed++; hold = 5; extinguishedAt = i; }
    }
  }
  const fire = fires[slot];
  const smoke = fire === 0 && extinguishedAt >= 0 ? Math.max(0, 1 - (end - extinguishedAt) / 5) : 0;
  const walking = completed < 3 && hold > 0 && hold <= 3;
  const nextSlot = (slot + 1) % 3;
  const walkProgress = walking ? (4 - hold) / 3 : 0;
  const startY = -targets[positions[slot]].lateral * 0.55;
  const endY = -targets[positions[nextSlot]].lateral * 0.55;
  const robotY = walking ? startY + (endY - startY) * walkProgress : startY;
  const looking = completed < 3 && hold === 5;
  const lookHeading = looking ? Math.atan2(-targets[positions[nextSlot]].lateral - startY, 2.7) : 0;
  const aiming = end === arrivedAt;
  return { targetIndex: positions[slot], slot, fires, fire, smoke, spraying: fire > 0 && !aiming, aiming, completed,
    walking, looking, lookHeading, nextSlot, walkProgress, walkDirection: Math.sign(endY - startY),
    walkHeading: completed < 3 && hold > 0 && hold <= 4 ? Math.sign(endY - startY) * Math.PI / 2 : 0,
    walkDistance: Math.abs(endY - startY), robotY };
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
