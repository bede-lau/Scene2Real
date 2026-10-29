// The demo's positive lateral direction is to the robot's right (-Y in G1 coordinates).
const MAX_POSE_ANGLE = Math.atan2(0.8, 2.5) * 180 / Math.PI;

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
