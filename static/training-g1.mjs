import * as THREE from './vendor/three.module.js';
import { modelEndpoint, poseBlend, sprayPoint } from './training-g1-motion.mjs';

// Display-only interpolation of the project's authored G1 reference poses.
export async function createG1View(host, { reducedMotion = false } = {}) {
  const response = await fetch('/assets/unitree_g1/training-g1.json?v=look-1', { cache: 'force-cache' });
  if (!response.ok) throw new Error('G1 model asset could not be loaded');
  const asset = await response.json();
  if (asset.schema !== 'scene2real-training-g1-visual-v1' || !asset.poses.rest || !asset.walk?.profiles || !asset.walk?.arm_indices || !Number.isInteger(asset.head_index)) throw new Error('Unsupported G1 visual asset');
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.25));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x101c25);
  scene.add(new THREE.HemisphereLight(0xdceefa, 0x35434a, 2.1));
  const light = new THREE.DirectionalLight(0xf5f8ff, 2.1); light.position.set(-2, -3, 6); scene.add(light);
  const camera = new THREE.PerspectiveCamera(48, 1, 0.05, 40);
  camera.up.set(0, 0, 1); camera.position.set(-1.6, -2.5, 1.9); camera.lookAt(1.2, 0, 0.9);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(9, 8), new THREE.MeshStandardMaterial({ color: 0x25343b, roughness: 0.95 }));
  ground.position.set(1.4, 0, -0.005); scene.add(ground);
  const grid = new THREE.GridHelper(8, 16, 0x52636c, 0x34444c);
  grid.rotation.x = Math.PI / 2; grid.position.set(1.2, 0, 0.001); scene.add(grid);
  const geometryCache = new Map();
  const materials = new Map();
  const meshes = asset.geometries.map(geom => {
    let geometry;
    if (geom.type === 'mesh') {
      if (!geometryCache.has(geom.mesh)) {
        const source = asset.meshes[String(geom.mesh)];
        geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(source.vertices, 3));
        geometry.setIndex(source.indices); geometry.computeVertexNormals(); geometryCache.set(geom.mesh, geometry);
      }
      geometry = geometryCache.get(geom.mesh);
    } else if (geom.type === 'cylinder') {
      geometry = new THREE.CylinderGeometry(geom.size[0], geom.size[0], geom.size[1] * 2, 12);
      geometry.rotateX(Math.PI / 2);
    } else throw new Error('Unsupported G1 geometry');
    const key = geom.rgba.join(',');
    if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({
      color: new THREE.Color(...geom.rgba.slice(0, 3)), roughness: 0.48, metalness: 0.25,
      transparent: geom.rgba[3] < 1, opacity: geom.rgba[3],
    }));
    const mesh = new THREE.Mesh(geometry, materials.get(key)); scene.add(mesh); return mesh;
  });
  const pedestalGeometry = new THREE.CylinderGeometry(0.22, 0.26, 0.55, 12);
  pedestalGeometry.rotateX(Math.PI / 2);
  const pedestalMaterial = new THREE.MeshStandardMaterial({ color: 0x52616c, roughness: 0.85 });
  const fireShape = new THREE.Shape();
  fireShape.moveTo(-0.16, 0); fireShape.quadraticCurveTo(-0.26, 0.18, -0.12, 0.34);
  fireShape.quadraticCurveTo(-0.06, 0.41, -0.1, 0.59); fireShape.quadraticCurveTo(0.05, 0.48, 0.05, 0.34);
  fireShape.quadraticCurveTo(0.16, 0.4, 0.13, 0.52); fireShape.quadraticCurveTo(0.28, 0.22, 0.16, 0.03);
  fireShape.quadraticCurveTo(0.08, -0.02, -0.16, 0);
  const flameGeometry = new THREE.ShapeGeometry(fireShape, 6);
  const flameMaterials = [0xef7133, 0xffbe54, 0xffecae].map((color, i) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity: [0.82, 0.9, 0.95][i], side: THREE.DoubleSide, depthWrite: false }));
  const targets = [-0.84, 0, 0.84].map(lateral => {
    const target = new THREE.Group(), pedestal = new THREE.Mesh(pedestalGeometry, pedestalMaterial);
    pedestal.position.z = 0.275; target.add(pedestal);
    const flames = new THREE.Group(); flames.position.z = 0.55;
    for (const rotation of [0, Math.PI / 2]) {
      const plane = new THREE.Group(); plane.rotation.z = rotation;
      for (let i = 0; i < 3; i++) {
        const flame = new THREE.Mesh(flameGeometry, flameMaterials[i]);
        flame.rotation.x = Math.PI / 2; flame.scale.setScalar([1, 0.72, 0.43][i]); plane.add(flame);
      }
      flames.add(plane);
    }
    target.add(flames); target.position.set(2.7, -lateral, 0); scene.add(target);
    return { target, flames };
  });
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.009, 1, 8, 1, true), new THREE.MeshBasicMaterial({ color: 0x94dfff, transparent: true, opacity: 0.24, side: THREE.DoubleSide, depthWrite: false }));
  scene.add(beam);
  const dropletCount = 64;
  const dropletGeometry = new THREE.BufferGeometry();
  dropletGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(dropletCount * 3), 3));
  const dot = document.createElement('canvas'); dot.width = dot.height = 32;
  const context = dot.getContext('2d');
  const gradient = context.createRadialGradient(16, 16, 1, 16, 16, 16);
  gradient.addColorStop(0, 'rgba(255,255,255,0.95)'); gradient.addColorStop(1, 'rgba(255,255,255,0)');
  context.fillStyle = gradient; context.fillRect(0, 0, 32, 32);
  const droplets = new THREE.Points(dropletGeometry, new THREE.PointsMaterial({ color: 0xb8eeff, size: 0.055, map: new THREE.CanvasTexture(dot), transparent: true, opacity: 0.9, depthWrite: false }));
  droplets.frustumCulled = false; scene.add(droplets);
  const smokeGeometry = new THREE.BufferGeometry();
  const smokeCount = 12;
  smokeGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(smokeCount * 3), 3));
  const smokeMaterial = new THREE.PointsMaterial({ color: 0xb8c3c8, size: 0.24, map: droplets.material.map, transparent: true, opacity: 0, depthWrite: false });
  const smoke = new THREE.Points(smokeGeometry, smokeMaterial);
  smoke.frustumCulled = false; scene.add(smoke);
  const teacherGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(1, 0, 0)]);
  const teacher = new THREE.Line(teacherGeometry, new THREE.LineDashedMaterial({ color: 0xd4dee4, dashSize: 0.12, gapSize: 0.08, transparent: true, opacity: 0.8 }));
  scene.add(teacher);
  const aimMarker = new THREE.Mesh(new THREE.SphereGeometry(0.035, 10, 8), new THREE.MeshBasicMaterial({ color: 0x75d9f2 })); scene.add(aimMarker);
  const q0 = new THREE.Quaternion(), q1 = new THREE.Quaternion(), qRest = new THREE.Quaternion(), qWalk = new THREE.Quaternion(), qNext = new THREE.Quaternion(), walkRotation = new THREE.Quaternion(), lookRotation = new THREE.Quaternion();
  const legLookup = new Map(asset.walk.leg_indices.map((index, i) => [index, i]));
  const armLookup = new Map(asset.walk.arm_indices.map((index, i) => [index, i]));
  const axis = new THREE.Vector3(0, 1, 0), start = new THREE.Vector3(), end = new THREE.Vector3();
  const temporary = new THREE.Vector3(), walkTemp = new THREE.Vector3(), direction = new THREE.Vector3(), up = new THREE.Vector3(0, 0, 1);
  let currentAngle = 0, currentFire = 1, currentArm = 0, currentY = 0, currentWalk = 0, currentHeading = 0, currentLook = 0, frame = null, playing = false, visible = true;
  let fromAngle = 0, fromFire = 1, fromArm = 0, fromY = 0, fromWalk = 0, fromHeading = 0, fromLook = 0, moveStarted = 0, lastPaint = -Infinity;
  let lastAim = { prediction: 0, expected: 0, lateral: 0, spraying: false, aiming: false, fire: 1, smoke: 0, fires: [1, 1, 1], slot: 1, robotY: 0, walkProgress: 0, walkHeading: 0, walkDistance: 0.462, lookHeading: 0 };

  function render(angle, aim, now = 0) {
    const blend = poseBlend(angle), a = asset.poses.center, b = asset.poses[blend.side];
    const walkFrames = asset.walk.profiles[aim.walkDistance > 0.7 ? 'long' : 'short'].frames;
    const walkFrame = Math.max(0, Math.min(1, currentWalk)) * (walkFrames.length - 1);
    const walkIndex = Math.floor(walkFrame), walkMix = walkFrame - walkIndex;
    const walkA = walkFrames[walkIndex], walkB = walkFrames[Math.min(walkIndex + 1, walkFrames.length - 1)];
    const drop = walkA.drop + (walkB.drop - walkA.drop) * walkMix;
    walkRotation.setFromAxisAngle(up, currentHeading);
    lookRotation.setFromAxisAngle(up, currentLook);
    for (let i = 0; i < meshes.length; i++) {
      const from = a.geoms[i], to = b.geoms[i], rest = asset.poses.rest.geoms[i], mesh = meshes[i];
      mesh.position.set(from[0], from[1], from[2]).lerp(temporary.set(to[0], to[1], to[2]), blend.weight);
      mesh.position.lerp(temporary.set(rest[0], rest[1], rest[2]), 1 - currentArm);
      q0.set(from[4], from[5], from[6], from[3]); q1.set(to[4], to[5], to[6], to[3]);
      qRest.set(rest[4], rest[5], rest[6], rest[3]);
      mesh.quaternion.copy(q0).slerp(q1, blend.weight).slerp(qRest, 1 - currentArm);
      const leg = legLookup.get(i);
      const freeArm = armLookup.get(i);
      if ((leg !== undefined || freeArm !== undefined) && currentWalk > 0 && currentWalk < 1) {
        const wa = leg !== undefined ? walkA.geoms[leg] : walkA.arm[freeArm];
        const wb = leg !== undefined ? walkB.geoms[leg] : walkB.arm[freeArm];
        temporary.set(wa[0], wa[1], wa[2]).lerp(walkTemp.set(wb[0], wb[1], wb[2]), walkMix);
        mesh.position.copy(temporary);
        qWalk.set(wa[4], wa[5], wa[6], wa[3]); qNext.set(wb[4], wb[5], wb[6], wb[3]);
        mesh.quaternion.copy(qWalk.slerp(qNext, walkMix));
      }
      if (i === asset.head_index) mesh.quaternion.premultiply(lookRotation);
      mesh.position.applyQuaternion(walkRotation); mesh.position.y += currentY; mesh.position.z -= drop;
      mesh.quaternion.premultiply(walkRotation);
    }
    start.fromArray(a.nozzle).lerp(temporary.fromArray(b.nozzle), blend.weight);
    start.lerp(temporary.fromArray(asset.poses.rest.nozzle), 1 - currentArm);
    start.applyQuaternion(walkRotation);
    start.y += currentY; start.z -= drop;
    const destination = [2.7, -aim.lateral, 0.9];
    end.fromArray(modelEndpoint(start.toArray(), destination, angle, aim.expected));
    direction.subVectors(end, start);
    beam.position.copy(start).add(end).multiplyScalar(0.5);
    beam.scale.set(1, direction.length(), 1);
    beam.quaternion.setFromUnitVectors(axis, direction.normalize());
    beam.visible = droplets.visible = aim.spraying === true;
    if (aim.spraying) {
      const phase = playing && !reducedMotion ? (now / 950) % 1 : 0;
      const from = start.toArray(), to = end.toArray();
      for (let i = 0; i < dropletCount; i++) dropletGeometry.attributes.position.setXYZ(i, ...sprayPoint(from, to, i, dropletCount, phase));
      dropletGeometry.attributes.position.needsUpdate = true;
    }
    targets.forEach(({ flames }, i) => {
      const intensity = i === aim.slot ? currentFire : aim.fires[i];
      flames.visible = intensity > 0.001;
      flames.scale.set(Math.sqrt(intensity), Math.sqrt(intensity), intensity * (playing && !reducedMotion ? 1 + 0.04 * Math.sin(now / 180) : 1));
    });
    smoke.visible = aim.smoke > 0;
    smoke.position.set(destination[0], destination[1], 0);
    smokeMaterial.opacity = 0.48 * aim.smoke;
    if (smoke.visible) {
      const drift = playing && !reducedMotion ? (now / 1600) % 1 : 0;
      for (let i = 0; i < smokeCount; i++) {
        const height = ((i / smokeCount + drift) % 1);
        smokeGeometry.attributes.position.setXYZ(i, Math.sin(i * 2.4) * 0.09 * height, Math.cos(i * 2.4) * 0.09 * height, 0.58 + height * 0.6);
      }
      smokeGeometry.attributes.position.needsUpdate = true;
    }
    aimMarker.position.copy(end);
    aimMarker.visible = aim.spraying === true || aim.aiming === true;
    teacherGeometry.attributes.position.setXYZ(0, start.x, start.y, start.z);
    teacherGeometry.attributes.position.setXYZ(1, ...destination);
    teacherGeometry.attributes.position.needsUpdate = true; teacher.computeLineDistances();
    renderer.render(scene, camera);
  }

  function schedule() {
    if (frame === null && visible && !document.hidden && !reducedMotion) frame = requestAnimationFrame(tick);
  }
  function tick(now) {
    frame = null;
    const progress = Math.min(1, (now - moveStarted) / 140);
    currentAngle = fromAngle + (lastAim.prediction - fromAngle) * (1 - (1 - progress) ** 3);
    currentFire = fromFire + (lastAim.fire - fromFire) * (1 - (1 - progress) ** 3);
    currentArm = fromArm + ((lastAim.spraying || lastAim.aiming ? 1 : 0) - fromArm) * (1 - (1 - progress) ** 3);
    currentY = fromY + (lastAim.robotY - fromY) * (1 - (1 - progress) ** 3);
    currentWalk = fromWalk + (lastAim.walkProgress - fromWalk) * (1 - (1 - progress) ** 3);
    currentHeading = fromHeading + (lastAim.walkHeading - fromHeading) * (1 - (1 - progress) ** 3);
    currentLook = fromLook + (lastAim.lookHeading - fromLook) * (1 - (1 - progress) ** 3);
    if (now - lastPaint >= 33 || (!playing && progress >= 1)) {
      render(currentAngle, lastAim, now); lastPaint = now;
    }
    if (playing || progress < 1) schedule();
  }
  function refreshVisibility() {
    if (!visible || document.hidden) {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null; currentAngle = lastAim.prediction; currentFire = lastAim.fire; currentArm = lastAim.spraying || lastAim.aiming ? 1 : 0; currentY = lastAim.robotY; currentWalk = lastAim.walkProgress; currentHeading = lastAim.walkHeading; currentLook = lastAim.lookHeading;
    } else {
      currentAngle = lastAim.prediction; currentFire = lastAim.fire; currentArm = lastAim.spraying || lastAim.aiming ? 1 : 0; currentY = lastAim.robotY; currentWalk = lastAim.walkProgress; currentHeading = lastAim.walkHeading; currentLook = lastAim.lookHeading; render(currentAngle, lastAim);
      if (playing) { fromAngle = currentAngle; fromFire = currentFire; fromArm = currentArm; fromY = currentY; fromWalk = currentWalk; fromHeading = currentHeading; fromLook = currentLook; moveStarted = performance.now() - 140; schedule(); }
    }
  }
  document.addEventListener('visibilitychange', refreshVisibility);
  const intersection = typeof IntersectionObserver === 'undefined' ? null : new IntersectionObserver(entries => {
    visible = entries[0].isIntersecting; refreshVisibility();
  });
  if (intersection) intersection.observe(host);

  function resize() {
    const width = Math.max(1, host.clientWidth), height = Math.max(1, host.clientHeight);
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix();
    render(currentAngle, lastAim);
  }
  const observer = new ResizeObserver(resize); observer.observe(host);
  resize();
  return {
    setAim(aim) {
      // At arrival both ends of the gait cycle are the same rest pose.
      if (lastAim.walkProgress === 1 && aim.walkProgress === 0) currentWalk = 0;
      lastAim = aim;
      if (reducedMotion || !visible || document.hidden) { currentAngle = aim.prediction; currentFire = aim.fire; currentArm = aim.spraying || aim.aiming ? 1 : 0; currentY = aim.robotY; currentWalk = aim.walkProgress; currentHeading = aim.walkHeading; currentLook = aim.lookHeading; if (visible && !document.hidden) render(currentAngle, aim); return; }
      fromAngle = currentAngle; fromFire = currentFire; fromArm = currentArm; fromY = currentY; fromWalk = currentWalk; fromHeading = currentHeading; fromLook = currentLook; moveStarted = performance.now(); schedule();
    },
    setPlayback(active) {
      playing = Boolean(active);
      if (playing) schedule();
      else if (frame === null && visible && !document.hidden) render(currentAngle, lastAim);
    },
    dispose() { if (frame !== null) cancelAnimationFrame(frame); observer.disconnect(); if (intersection) intersection.disconnect(); document.removeEventListener('visibilitychange', refreshVisibility); renderer.dispose(); },
  };
}
