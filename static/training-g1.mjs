import * as THREE from './vendor/three.module.js';
import { modelEndpoint, poseBlend } from './training-g1-motion.mjs';

// Display-only interpolation of the project's authored G1 reference poses.
export async function createG1View(host, { reducedMotion = false } = {}) {
  const response = await fetch('/assets/unitree_g1/training-g1.json', { cache: 'force-cache' });
  if (!response.ok) throw new Error('G1 model asset could not be loaded');
  const asset = await response.json();
  if (asset.schema !== 'scene2real-training-g1-visual-v1') throw new Error('Unsupported G1 visual asset');
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
  const pedestal = new THREE.Mesh(pedestalGeometry, new THREE.MeshStandardMaterial({ color: 0x52616c, roughness: 0.85 }));
  const target = new THREE.Group(); target.add(pedestal); pedestal.position.z = 0.275;
  const halo = new THREE.Mesh(new THREE.RingGeometry(0.18, 0.205, 32), new THREE.MeshBasicMaterial({ color: 0xbba8ff, side: THREE.DoubleSide }));
  halo.position.z = 0.56; target.add(halo);
  const marker = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 12), new THREE.MeshStandardMaterial({ color: 0xbba8ff, emissive: 0x473764, emissiveIntensity: 0.65, roughness: 0.5 }));
  marker.position.z = 0.9; target.add(marker); scene.add(target);
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1, 8), new THREE.MeshBasicMaterial({ color: 0x75d9f2, transparent: true, opacity: 0.9 }));
  scene.add(beam);
  const teacherGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(1, 0, 0)]);
  const teacher = new THREE.Line(teacherGeometry, new THREE.LineDashedMaterial({ color: 0xd4dee4, dashSize: 0.12, gapSize: 0.08, transparent: true, opacity: 0.8 }));
  scene.add(teacher);
  const aimMarker = new THREE.Mesh(new THREE.SphereGeometry(0.035, 10, 8), new THREE.MeshBasicMaterial({ color: 0x75d9f2 })); scene.add(aimMarker);
  const q0 = new THREE.Quaternion(), q1 = new THREE.Quaternion();
  const axis = new THREE.Vector3(0, 1, 0), start = new THREE.Vector3(), end = new THREE.Vector3();
  const temporary = new THREE.Vector3(), direction = new THREE.Vector3();
  let currentAngle = 0, frame = null, lastAim = { prediction: 0, expected: 0, lateral: 0 };

  function render(angle, aim) {
    const blend = poseBlend(angle), a = asset.poses.center, b = asset.poses[blend.side];
    for (let i = 0; i < meshes.length; i++) {
      const from = a.geoms[i], to = b.geoms[i], mesh = meshes[i];
      mesh.position.set(from[0], from[1], from[2]).lerp(temporary.set(to[0], to[1], to[2]), blend.weight);
      q0.set(from[4], from[5], from[6], from[3]); q1.set(to[4], to[5], to[6], to[3]);
      mesh.quaternion.copy(q0).slerp(q1, blend.weight);
    }
    start.fromArray(a.nozzle).lerp(temporary.fromArray(b.nozzle), blend.weight);
    const destination = [2.7, -aim.lateral, 0.9];
    target.position.set(destination[0], destination[1], 0);
    end.fromArray(modelEndpoint(start.toArray(), destination, angle, aim.expected));
    direction.subVectors(end, start);
    beam.position.copy(start).add(end).multiplyScalar(0.5);
    beam.scale.set(1, direction.length(), 1);
    beam.quaternion.setFromUnitVectors(axis, direction.normalize());
    aimMarker.position.copy(end);
    teacherGeometry.attributes.position.setXYZ(0, start.x, start.y, start.z);
    teacherGeometry.attributes.position.setXYZ(1, ...destination);
    teacherGeometry.attributes.position.needsUpdate = true; teacher.computeLineDistances();
    renderer.render(scene, camera);
  }

  function resize() {
    const width = Math.max(1, host.clientWidth), height = Math.max(1, host.clientHeight);
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix();
    render(currentAngle, lastAim);
  }
  const observer = new ResizeObserver(resize); observer.observe(host);
  resize();
  return {
    setAim(aim) {
      lastAim = aim;
      if (frame !== null) cancelAnimationFrame(frame);
      if (reducedMotion) { currentAngle = aim.prediction; render(currentAngle, aim); return; }
      const from = currentAngle, started = performance.now();
      const tick = now => {
        const progress = Math.min(1, (now - started) / 140);
        currentAngle = from + (aim.prediction - from) * (1 - (1 - progress) ** 3);
        render(currentAngle, lastAim);
        frame = progress < 1 ? requestAnimationFrame(tick) : null;
      };
      frame = requestAnimationFrame(tick);
    },
    dispose() { if (frame !== null) cancelAnimationFrame(frame); observer.disconnect(); renderer.dispose(); },
  };
}
