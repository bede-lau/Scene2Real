import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
let current, manifest, config, sessionId, scene, renderer, inputRenderer, observerCamera, robotCamera, controls;
let meshes = [], fireGroup, flameMaterial, fireLight, sprayLine, sprayParticles, sparkPositions, cameraMode = 'observer';
let recorder, recordingCanvas, recordingContext, recordingChunks = [], recordingUrl, recordingStarted = 0, previousWall = performance.now();
let busy = false, renderingReady = false, trackingHistory = [], lastRevision = -1, lastStateTime = 0;
const meshCache = new Map(), vTemp = new T.Vector3(), qTemp = new T.Quaternion();
const API = '/api/live';
const cap = value => value ? value[0].toUpperCase() + value.slice(1) : '—';

async function api(path, body, options = {}) {
  const response = await fetch(path, body === undefined ? options : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), ...options
  });
  let result;
  try { result = await response.json(); } catch { throw new Error('The server returned an unreadable response.'); }
  if (!response.ok) {
    const detail = result.detail;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail || 'Request failed'));
  }
  return result;
}
function notify(message = '', error = false) {
  $('#notice').textContent = message;
  $('#notice').classList.toggle('error', error);
}
function setConnection(connected) {
  $('#connection-dot').className = connected ? 'connected' : 'failed';
  $('#connection-label').textContent = connected ? 'Physics connected' : 'Disconnected';
}
function acceptState(state) {
  if (current && state.session_id === current.session_id && state.seq < current.seq) return;
  current = state;
  lastStateTime = performance.now();
  if (state.scene_revision !== lastRevision) {
    lastRevision = state.scene_revision; trackingHistory = [];
  }
  trackingHistory.push(Number(state.metrics.tracking_error_rad || 0));
  if (trackingHistory.length > 150) trackingHistory.shift();
  renderUI();
}
async function command(endpoint, body) {
  if (!sessionId || busy) return;
  busy = true;
  document.body.dataset.busy = 'true';
  try {
    const result = await api(API + '/' + sessionId + '/' + endpoint, body);
    acceptState(result);
    notify(config.cosmos_enabled ? '' : 'Local physics preview · Cosmos is disabled · Automatic spray is off');
  } catch (error) { notify(error.message, true); }
  finally { busy = false; document.body.dataset.busy = 'false'; }
}
function renderUI() {
  if (!current) return;
  const state = current, decision = state.decision || {}, metrics = state.metrics || {}, spray = state.spray || {};
  $$('#scenarios button').forEach(button => button.setAttribute('aria-pressed', button.dataset.scenario === state.scenario));
  $$('#pose-controls button').forEach(button => button.setAttribute('aria-pressed', button.dataset.pose === state.pose));
  if (document.activeElement !== $('#fire-position')) {
    const y = state.fire.intensity > 0 ? state.fire.position[1] : 0;
    $('#fire-position').value = y;
    $('#fire-position-value').textContent = y.toFixed(2) + ' m';
  }
  $('#fire-position').disabled = state.scenario === 'none';
  $('#obstacle').checked = state.obstacle ?? state.scenario === 'obscured';
  $('#pause-button span').textContent = state.paused ? 'Resume physics' : 'Pause physics';
  $('#pause-button').setAttribute('aria-pressed', state.paused);
  $('#sim-clock').textContent = Math.floor(state.sim_time / 60).toString().padStart(2, '0') + ':' + (state.sim_time % 60).toFixed(2).padStart(5, '0');
  $('#motion-label').textContent = 'Predefined motion · ' + cap(state.pose) + (state.scenario === 'wrong' ? ' · Wrong aim override' : '');
  const intensity = Math.round(state.fire.intensity * 100);
  $('#intensity-value').innerHTML = intensity + '<span>%</span>';
  $('#intensity-bar').style.width = intensity + '%';
  $('#angle-value').innerHTML = state.fire.intensity > 0 && Number.isFinite(metrics.angle_error_deg) ? metrics.angle_error_deg.toFixed(1) + '<span>°</span>' : '—';
  $('#hit-value').innerHTML = Number(metrics.hit_s || 0).toFixed(2) + '<span> s</span>';
  $('#miss-value').innerHTML = Number(metrics.miss_s || 0).toFixed(2) + '<span> s</span>';
  const errorDeg = Number(metrics.tracking_error_rad || 0) * 180 / Math.PI;
  $('#tracking-value').textContent = errorDeg.toFixed(2) + '°';
  const max = Math.max(.15, ...trackingHistory);
  $('#tracking-line').setAttribute('points', trackingHistory.map((v, i) => (i / Math.max(1, trackingHistory.length - 1) * 600).toFixed(1) + ',' + (56 - v / max * 49).toFixed(1)).join(' '));
  const badge = $('#spray-badge');
  badge.textContent = !spray.on ? 'SPRAY OFF' : spray.hit ? 'SPRAY HIT' : spray.blocked ? 'SPRAY BLOCKED' : 'SPRAY MISS';
  badge.className = 'status-badge ' + (spray.on ? spray.hit ? 'hit' : 'miss' : '');
  $('#ray-result').textContent = !spray.on ? 'Inactive' : spray.hit ? 'Fire hit' : spray.blocked ? 'Obstacle blocked' : 'Miss';
  const statuses = {
    idle: config.cosmos_enabled ? 'Awaiting observation' : 'Cosmos disabled',
    pending: 'Reading robot camera…', ready: 'Aim ' + cap(decision.pose),
    no_fire: 'No fire · Spray stopped', uncertain: 'Uncertain · Spray stopped',
    failed: 'Inference failed · Spray stopped', invalid: 'Invalid response · Spray stopped',
    stale: 'Stale decision · Spray stopped', stopped: 'Spray stopped'
  };
  $('#decision-title').textContent = statuses[decision.status] || cap(decision.status);
  $('#decision-detail').textContent = !config.cosmos_enabled && decision.status === 'idle'
    ? 'Pose previews run in MuJoCo. Automatic spraying requires a real camera decision.'
    : decision.detail || 'No camera decision has authorized spraying.';
  $('#decision-dot').className = 'decision-dot ' + (decision.status || '');
  $('#response-time').textContent = decision.latency_s == null ? '—' : Number(decision.latency_s).toFixed(2) + ' s';
  $('#snapshot-value').textContent = decision.snapshot_id || '—';
  $('#raw-response').textContent = decision.raw_text || (decision.observations ? JSON.stringify(decision.observations, null, 2) : 'No inference response');
  $('#analyse-button').disabled = !config.cosmos_enabled || decision.status === 'pending' || !renderingReady;
  $('#analyse-button span').textContent = decision.status === 'pending' ? 'Observing…' : 'Observe with Cosmos';
  $('#camera-state').textContent = 'Frame ' + state.seq;
  $('#evidence-id').textContent = 'Session ' + state.session_id;
}
function setQuat(object, values) { object.quaternion.set(values[1], values[2], values[3], values[0]); }
function makeMaterial(geom) {
  const color = new T.Color(...geom.rgba.slice(0, 3));
  if (geom.name === 'live_floor') color.setHex(0x737a7a);
  if (geom.name === 'live_back_wall') color.setHex(0x77858b);
  const metal = geom.category === 'robot' || geom.category === 'tool' ? .35 : geom.name.includes('rack') ? .65 : .08;
  return new T.MeshStandardMaterial({ color, metalness: metal, roughness: geom.category === 'robot' ? .4 : .82,
    transparent: geom.rgba[3] < 1, opacity: geom.rgba[3], side: geom.type === 'plane' ? T.DoubleSide : T.FrontSide });
}
async function geometryFor(geom) {
  const s = geom.size;
  switch (geom.type) {
    case 'mesh': {
      if (!meshCache.has(geom.mesh_url)) meshCache.set(geom.mesh_url, fetch(geom.mesh_url).then(r => {
        if (!r.ok) throw new Error('Robot mesh failed to load.');
        return r.json();
      }).then(data => {
        const geometry = new T.BufferGeometry();
        geometry.setAttribute('position', new T.Float32BufferAttribute(data.vertices, 3));
        geometry.setIndex(data.indices); geometry.computeVertexNormals(); return geometry;
      }));
      return meshCache.get(geom.mesh_url);
    }
    case 'plane': return new T.PlaneGeometry(30, 30);
    case 'box': return new T.BoxGeometry(s[0] * 2, s[1] * 2, s[2] * 2);
    case 'sphere': return new T.SphereGeometry(s[0], 24, 16);
    case 'ellipsoid': { const g = new T.SphereGeometry(1, 24, 16); g.scale(...s); return g; }
    case 'cylinder': { const g = new T.CylinderGeometry(s[0], s[0], s[1] * 2, 32); g.rotateX(Math.PI / 2); return g; }
    case 'capsule': { const g = new T.CapsuleGeometry(s[0], 2 * s[1], 6, 16); g.rotateX(Math.PI / 2); return g; }
    default: throw new Error('Unsupported model geometry: ' + geom.type);
  }
}
function box(size, pos, color, options = {}) {
  const mesh = new T.Mesh(new T.BoxGeometry(...size), new T.MeshStandardMaterial({ color, roughness: .75, metalness: .25, ...options }));
  mesh.position.set(...pos); mesh.castShadow = true; mesh.receiveShadow = true; scene.add(mesh); return mesh;
}
function warehouseDetails() {
  // Visual finishing around the canonical collidable warehouse, in SI Z-up.
  const stripeMaterial = new T.MeshStandardMaterial({ color: 0xd3d876, roughness: .8 });
  for (const y of [-1.5, 1.5]) {
    const line = new T.Mesh(new T.PlaneGeometry(8.8, .035), stripeMaterial);
    line.position.set(2.1, y, .007); scene.add(line);
  }
  const jointMat = new T.LineBasicMaterial({ color: 0x60696b, transparent: true, opacity: .4 });
  for (let x = -6; x < 12; x += 2) {
    const geo = new T.BufferGeometry().setFromPoints([new T.Vector3(x, -7, .004), new T.Vector3(x, 7, .004)]);
    scene.add(new T.Line(geo, jointMat));
  }
  for (let y = -6; y < 7; y += 2) {
    const geo = new T.BufferGeometry().setFromPoints([new T.Vector3(-7, y, .004), new T.Vector3(12, y, .004)]);
    scene.add(new T.Line(geo, jointMat));
  }
  // Architectural details outside the robot workspace, not movable obstacles.
  for (let x = -2; x <= 7; x += 3) {
    for (const y of [-4.5, 4.5]) {
      box([.14, .18, 4.8], [x, y, 2.4], 0x4c5c63);
      box([.17, .21, .45], [x, y, .225], 0xd3c966);
    }
    box([.14, 9.2, .19], [x, 0, 4.7], 0x53636b);
    const lightPanel = box([.8, 2.1, .045], [x, 0, 4.55], 0xe7f1ed, { emissive: 0xe2f2ed, emissiveIntensity: .75 });
    lightPanel.castShadow = false;
  }
  // Warehouse wall at the physical back-wall surface.
  for (let y = -4; y <= 4; y += 1.2) box([.025, .018, 3.1], [6.88, y, 1.58], 0x56686e);
  for (const y of [-3.5, 3.5]) {
    box([.025, 1.7, .65], [6.87, y, 2.65], 0xc9e2e4, { emissive: 0xbed9df, emissiveIntensity: .3, metalness: .1 });
    box([.04, 1.75, .025], [6.84, y, 2.65], 0x53646c);
  }
  // High-contrast floor targets and labels are authored geometry, not observations.
  for (const [label, anchor] of Object.entries(manifest.targets)) {
    const ring = new T.Mesh(new T.RingGeometry(.43, .46, 64), new T.MeshStandardMaterial({ color: 0xc5d478, roughness: .9, side: T.DoubleSide }));
    ring.position.set(anchor[0], anchor[1], .034); scene.add(ring);
    const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 96;
    const g = canvas.getContext('2d'); g.clearRect(0, 0, 256, 96);
    g.font = '600 42px sans-serif'; g.fillStyle = '#e4e9d7'; g.textAlign = 'center'; g.fillText(label.toUpperCase(), 128, 59);
    const mat = new T.MeshBasicMaterial({ map: new T.CanvasTexture(canvas), transparent: true, opacity: .85, depthWrite: false, side: T.DoubleSide });
    const tag = new T.Mesh(new T.PlaneGeometry(.7, .26), mat); tag.position.set(anchor[0] + .57, anchor[1], .008);
    tag.rotation.z = Math.PI / 2; scene.add(tag);
  }
  // Rack top shelf freight; static scene decoration has no role in control.
  for (const y of [-2.3, 2.3]) for (const x of [1.9, 2.65, 3.15]) {
    box([.43, .48, .43], [x, y, 1.35], 0x9a896b);
    box([.43, .48, .032], [x, y, 1.38], 0xb8a78b);
    box([.43, .022, .43], [x, y, 1.35], 0x746955);
    box([.02, .48, .43], [x, y, 1.35], 0x746955);
  }
}
function makeFire() {
  fireGroup = new T.Group(); scene.add(fireGroup);
  flameMaterial = new T.ShaderMaterial({
    uniforms: { time: { value: 0 }, strength: { value: 1 } }, transparent: true, depthWrite: false, side: T.DoubleSide,
    blending: T.AdditiveBlending,
    vertexShader: 'varying vec2 uvv; void main(){uvv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader: [
      'varying vec2 uvv; uniform float time; uniform float strength;',
      'float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}',
      'float noise(vec2 p){vec2 i=floor(p),f=fract(p); f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}',
      'void main(){vec2 p=uvv;float n=noise(vec2(p.x*5.,p.y*7.-time*2.4))*.65+noise(vec2(p.x*11.,p.y*13.-time*4.))*.35;',
      'float x=abs(p.x-.5+sin(p.y*8.-time*3.)*.055*p.y);float width=(1.-p.y)*.44*(.6+n*.7);',
      'float mask=smoothstep(width+.04,width-.08,x)*smoothstep(1.,.55+n*.22,p.y)*smoothstep(0.,.07,p.y);',
      'float core=pow(max(0.,1.-x/(width+.001)),2.)*(1.-p.y);vec3 color=mix(vec3(1.,.12,.005),vec3(1.,.85,.32),core);',
      'gl_FragColor=vec4(color,mask*.86*strength);}'
    ].join('\n')
  });
  const geometry = new T.PlaneGeometry(.72, .98); geometry.rotateX(Math.PI / 2); geometry.translate(0, 0, .49);
  for (let i = 0; i < 3; i++) {
    const flame = new T.Mesh(geometry, flameMaterial); flame.rotation.z = i * Math.PI / 3; fireGroup.add(flame);
  }
  fireLight = new T.PointLight(0xff7326, 6, 5, 2); fireLight.position.z = .3; fireGroup.add(fireLight);
  const smokeGeo = new T.SphereGeometry(.1, 12, 8);
  for (let i = 0; i < 10; i++) {
    const puff = new T.Mesh(smokeGeo, new T.MeshBasicMaterial({ color: 0x30383c, transparent: true, opacity: .10, depthWrite: false }));
    puff.userData.phase = i / 10; fireGroup.add(puff);
  }
  const sprayGeo = new T.BufferGeometry().setFromPoints([new T.Vector3(), new T.Vector3()]);
  sprayLine = new T.Line(sprayGeo, new T.LineBasicMaterial({ color: 0x9fddff, transparent: true, opacity: .65 }));
  sprayLine.visible = false; scene.add(sprayLine);
  sparkPositions = new Float32Array(240 * 3);
  const pg = new T.BufferGeometry(); pg.setAttribute('position', new T.BufferAttribute(sparkPositions, 3));
  sprayParticles = new T.Points(pg, new T.PointsMaterial({ size: .025, color: 0xb8eaff, transparent: true, opacity: .8, depthWrite: false }));
  sprayParticles.visible = false; scene.add(sprayParticles);
}
async function initRenderer() {
  const host = $('#observer');
  renderer = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
  renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.35;
  host.prepend(renderer.domElement); renderer.domElement.setAttribute('aria-label', 'Live MuJoCo Unitree G1 warehouse scene');
  scene = new T.Scene(); scene.background = new T.Color(0xa2b1b9); scene.fog = new T.Fog(0xa2b1b9, 15, 40);
  scene.add(new T.HemisphereLight(0xe5f1fa, 0x626359, 2.0));
  const sunlight = new T.DirectionalLight(0xfff7e9, 3.3); sunlight.position.set(0, -3, 7);
  sunlight.castShadow = true; sunlight.shadow.mapSize.set(2048, 2048);
  Object.assign(sunlight.shadow.camera, { left: -5, right: 8, top: 5, bottom: -5, near: .1, far: 20 });
  sunlight.shadow.normalBias = .025; sunlight.shadow.bias = -.0001; sunlight.target.position.set(2, 0, 0);
  scene.add(sunlight, sunlight.target);
  const fill = new T.DirectionalLight(0xc2e3ff, 1.4); fill.position.set(-4, 4, 4); scene.add(fill);
  observerCamera = new T.PerspectiveCamera(44, 1, .03, 100); observerCamera.up.set(0, 0, 1);
  controls = new OrbitControls(observerCamera, renderer.domElement); controls.enableDamping = !reducedMotion;
  controls.minDistance = 1.0; controls.maxDistance = 16; controls.maxPolarAngle = Math.PI * .48;
  homeCamera();
  robotCamera = new T.PerspectiveCamera(manifest.camera.fovy, 1.6, .025, 60);
  inputRenderer = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  inputRenderer.setSize(640, 400, false); inputRenderer.shadowMap.enabled = true; inputRenderer.shadowMap.type = T.PCFSoftShadowMap;
  inputRenderer.toneMapping = T.ACESFilmicToneMapping; inputRenderer.toneMappingExposure = 1.35;
  $('#robot-camera').append(inputRenderer.domElement); $('#camera-placeholder').hidden = true;
  const geometryList = await Promise.all(manifest.geoms.map(geometryFor));
  meshes = manifest.geoms.map((geom, i) => {
    const mesh = new T.Mesh(geometryList[i], makeMaterial(geom)); mesh.userData.geom = geom;
    mesh.visible = geom.category !== 'fire' && !(geom.category === 'robot' && geom.group === 1);
    mesh.castShadow = geom.type !== 'plane'; mesh.receiveShadow = true;
    scene.add(mesh); return mesh;
  });
  warehouseDetails(); makeFire();
  new ResizeObserver(resize).observe(host); resize();
  renderingReady = true; $('#scene-loading').hidden = true;
  requestAnimationFrame(tick);
}
function homeCamera() {
  observerCamera.position.set(-2.8, -3.4, 2.3);
  controls.target.set(1.25, 0, .80); controls.update();
}
function resize() {
  if (!renderer) return;
  const host = $('#observer'), w = host.clientWidth, h = host.clientHeight;
  renderer.setSize(w, h); observerCamera.aspect = w / h; observerCamera.updateProjectionMatrix();
}
function applyState() {
  if (!current || !renderingReady) return;
  for (let i = 0; i < meshes.length; i++) {
    const pose = current.geoms[i], mesh = meshes[i]; if (!pose) continue;
    mesh.position.set(pose[0], pose[1], pose[2]); mesh.quaternion.set(pose[4], pose[5], pose[6], pose[3]);
  }
  robotCamera.position.set(...current.camera.position); setQuat(robotCamera, current.camera.quaternion);
  if (fireGroup) {
    const fire = current.fire;
    fireGroup.visible = fire.intensity > 0;
    fireGroup.position.set(fire.position[0], fire.position[1], fire.position[2] - .32);
    fireGroup.scale.setScalar(Math.max(.01, Math.sqrt(fire.intensity)));
    flameMaterial.uniforms.time.value = reducedMotion || current.paused ? 0 : current.sim_time;
    flameMaterial.uniforms.strength.value = Math.min(1, fire.intensity * 2);
  }
}
function tick(now) {
  requestAnimationFrame(tick);
  const dt = Math.min(.06, (now - previousWall) / 1000); previousWall = now;
  applyState();
  if (current) {
    const fire = current.fire; fireGroup.visible = fire.intensity > 0;
    fireGroup.position.set(fire.position[0], fire.position[1], fire.position[2] - .32);
    fireGroup.scale.setScalar(Math.max(.01, Math.sqrt(fire.intensity)));
    flameMaterial.uniforms.time.value = reducedMotion || current.paused ? 0 : current.sim_time;
    flameMaterial.uniforms.strength.value = Math.min(1, fire.intensity * 2);
    fireLight.intensity = 4 + (reducedMotion ? 0 : Math.sin(current.sim_time * 12) * .7);
    for (const puff of fireGroup.children) if (puff.userData.phase != null) {
      const phase = (puff.userData.phase + (reducedMotion ? .15 : current.sim_time * .22)) % 1;
      puff.position.set(Math.sin(phase * 8 + puff.userData.phase) * .12 * phase, Math.cos(phase * 6) * .07, .65 + phase * 1.4);
      puff.scale.setScalar(1 + phase * 2.3); puff.material.opacity = .12 * (1 - phase);
    }
    const spray = current.spray; sprayLine.visible = sprayParticles.visible = !!spray.on;
    if (spray.on && spray.point) {
      const origin = current.nozzle.slice(0, 3), end = spray.point;
      sprayLine.geometry.attributes.position.setXYZ(0, ...origin); sprayLine.geometry.attributes.position.setXYZ(1, ...end);
      sprayLine.geometry.attributes.position.needsUpdate = true;
      const direction = new T.Vector3(...end).sub(new T.Vector3(...origin)), length = direction.length();
      for (let i = 0; i < 240; i++) {
        const alpha = (i / 240 + current.sim_time * 1.8) % 1;
        const scatter = .025 * alpha;
        sparkPositions[i * 3] = origin[0] + direction.x * alpha + Math.sin(i * 17) * scatter;
        sparkPositions[i * 3 + 1] = origin[1] + direction.y * alpha + Math.cos(i * 13) * scatter;
        sparkPositions[i * 3 + 2] = origin[2] + direction.z * alpha + Math.sin(i * 7) * scatter;
      }
      sprayParticles.geometry.attributes.position.needsUpdate = true;
    }
    controls.update();
    if (cameraMode === 'robot') {
      const old = robotCamera.aspect; robotCamera.aspect = observerCamera.aspect; robotCamera.updateProjectionMatrix();
      renderer.render(scene, robotCamera); robotCamera.aspect = old; robotCamera.updateProjectionMatrix();
    } else renderer.render(scene, observerCamera);
    inputRenderer.render(scene, robotCamera);
  }
  if (recorder?.state === 'recording') {
    drawRecordingFrame();
    $('#record-button').lastChild.textContent = ' Stop · ' + Math.floor((now - recordingStarted) / 1000) + 's';
  }
}
function drawRecordingFrame() {
  if (!recordingContext || !current) return;
  const g = recordingContext, w = recordingCanvas.width, h = recordingCanvas.height;
  g.fillStyle = '#131d25'; g.fillRect(0, 0, w, h);
  const source = renderer.domElement, ratio = Math.min(w / source.width, (h - 88) / source.height);
  const dw = source.width * ratio, dh = source.height * ratio;
  g.drawImage(source, (w - dw) / 2, 42 + (h - 88 - dh) / 2, dw, dh);
  g.font = '600 19px sans-serif'; g.fillStyle = '#f0f5f8';
  g.fillText('Scene2Real  /  MuJoCo G1 rehearsal', 20, 28);
  g.font = '14px sans-serif'; g.textAlign = 'right'; g.fillStyle = '#d4e9b2';
  g.fillText('Predefined motion · Fixed base · No trained robot policy', w - 20, 27); g.textAlign = 'left';
  g.fillStyle = '#e2eaf0'; g.font = '15px sans-serif';
  g.fillText('Scenario: ' + current.scenario + '  |  Pose: ' + current.pose + '  |  t=' + current.sim_time.toFixed(2) + 's', 20, h - 26);
  g.textAlign = 'right'; g.fillStyle = current.spray.on ? '#ffbf8a' : '#c1d2de';
  g.fillText((config.cosmos_enabled ? 'Cosmos ' + current.decision.status : 'Cosmos disabled') + '  |  Spray ' + (current.spray.on ? current.spray.hit ? 'HIT' : 'MISS / BLOCKED' : 'OFF') + '  |  Fire ' + Math.round(current.fire.intensity * 100) + '%', w - 20, h - 26);
  g.textAlign = 'left';
  if (cameraMode === 'observer') {
    const pw = 256, ph = 160, px = w - pw - 20, py = h - ph - 64;
    g.fillStyle = '#18232d'; g.fillRect(px - 2, py - 22, pw + 4, ph + 24);
    g.drawImage(inputRenderer.domElement, px, py, pw, ph);
    g.fillStyle = '#e3edf5'; g.font = '11px sans-serif'; g.fillText('ROBOT CAMERA · SYNTHETIC INPUT', px + 7, py - 7);
  }
}
async function observe() {
  if (!config.cosmos_enabled || !renderingReady || !current) return;
  // Capture both pixel data and metadata from the SAME applied server state.
  const snapshotState = current;
  applyState(); inputRenderer.render(scene, robotCamera);
  const image = inputRenderer.domElement.toDataURL('image/jpeg', .90);
  const snapshotId = 'camera-' + crypto.randomUUID().slice(0, 12);
  $('#snapshot-image').src = image; $('#snapshot-section').hidden = false;
  await command('analyse', {
    snapshot_id: snapshotId, image, state_seq: snapshotState.seq, scene_revision: snapshotState.scene_revision,
    camera_pose: { position: snapshotState.camera.position, quaternion: snapshotState.camera.quaternion }
  });
}
async function saveCameraFrame() {
  if (!renderingReady || !current) return;
  const snapshotState = current;
  applyState(); inputRenderer.render(scene, robotCamera);
  const image = inputRenderer.domElement.toDataURL('image/jpeg', .90);
  const snapshotId = 'camera-' + crypto.randomUUID().slice(0, 12);
  $('#save-frame').disabled = true;
  try {
    const result = await api(API + '/' + sessionId + '/snapshot', {
      snapshot_id: snapshotId, image, state_seq: snapshotState.seq, scene_revision: snapshotState.scene_revision,
      camera_pose: { position: snapshotState.camera.position, quaternion: snapshotState.camera.quaternion }
    });
    acceptState(result);
    $('#snapshot-image').src = result.saved_snapshot?.image_url || image;
    $('#snapshot-section').hidden = false;
    notify('Robot-camera frame saved to run evidence. No inference was requested.');
  } catch (error) { notify(error.message, true); }
  finally { $('#save-frame').disabled = false; }
}
async function toggleRecording() {
  if (recorder?.state === 'recording') { recorder.stop(); return; }
  if (!renderer || !window.MediaRecorder || !renderer.domElement.captureStream) { notify('This browser cannot record the simulation canvas.', true); return; }
  const mimeType = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].find(t => MediaRecorder.isTypeSupported(t));
  if (!mimeType) { notify('This browser does not support WebM recording.', true); return; }
  recordingChunks = [];
  recordingCanvas = document.createElement('canvas'); recordingCanvas.width = 1280; recordingCanvas.height = 800;
  recordingContext = recordingCanvas.getContext('2d'); drawRecordingFrame();
  const stream = recordingCanvas.captureStream(30);
  recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 5_000_000 });
  recorder.ondataavailable = event => { if (event.data.size) recordingChunks.push(event.data); };
  recorder.onstop = async () => {
    stream.getTracks().forEach(track => track.stop());
    const blob = new Blob(recordingChunks, { type: mimeType });
    if (recordingUrl) URL.revokeObjectURL(recordingUrl);
    recordingUrl = URL.createObjectURL(blob);
    const download = $('#video-download'); download.href = recordingUrl; download.download = 'scene2real-' + sessionId + '.webm'; download.hidden = false;
    $('#record-button').classList.remove('recording'); $('#record-button').innerHTML = '<span class="record-dot"></span>Record view';
    try {
      const response = await fetch(API + '/' + sessionId + '/recording', { method: 'POST', headers: { 'Content-Type': 'video/webm' }, body: blob });
      if (!response.ok) throw new Error('Recording download is ready; server archival failed.');
      const result = await response.json(); download.href = result.url;
      notify('Recording saved with this run’s evidence.');
    } catch (error) { notify(error.message, true); }
  };
  recorder.start(1000); recordingStarted = performance.now();
  $('#record-button').classList.add('recording'); $('#record-button').innerHTML = '<span class="record-dot"></span> Stop recording';
}
function setView(view) {
  cameraMode = view; controls.enabled = view === 'observer';
  $('#observer-view').setAttribute('aria-pressed', view === 'observer');
  $('#robot-view').setAttribute('aria-pressed', view === 'robot');
  $('#view-label').textContent = view === 'observer' ? 'OBSERVER' : 'ROBOT CAMERA';
}
$$('#scenarios button').forEach(button => button.addEventListener('click', async () => {
  await command('scene', { scenario: button.dataset.scenario });
}));
$$('#pose-controls button').forEach(button => button.addEventListener('click', () => command('control', { action: 'pose', pose: button.dataset.pose })));
$('#fire-position').addEventListener('input', event => { $('#fire-position-value').textContent = Number(event.target.value).toFixed(2) + ' m'; });
$('#fire-position').addEventListener('change', event => command('scene', { scenario: current.scenario, fire_y: Number(event.target.value), obstacle: $('#obstacle').checked }));
$('#obstacle').addEventListener('change', event => command('scene', { scenario: current.scenario, fire_y: current.fire.position[1], obstacle: event.target.checked }));
$('#pause-button').addEventListener('click', () => command('control', { action: current.paused ? 'resume' : 'pause' }));
$('#reset-button').addEventListener('click', () => command('control', { action: 'reset' }));
$('#stop-button').addEventListener('click', () => command('control', { action: 'stop' }));
$('#observer-view').addEventListener('click', () => setView('observer'));
$('#robot-view').addEventListener('click', () => setView('robot'));
$('#home-view').addEventListener('click', () => { setView('observer'); homeCamera(); });
$('#analyse-button').addEventListener('click', observe);
$('#record-button').addEventListener('click', toggleRecording);
$('#save-frame').addEventListener('click', saveCameraFrame);
$('#evidence-download').addEventListener('click', async event => {
  event.preventDefault(); if (!current) return;
  try {
    const evidence = await api(current.evidence_url);
    const url = URL.createObjectURL(new Blob([JSON.stringify(evidence, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'scene2real-' + sessionId + '-evidence.json'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch (error) { notify(error.message, true); }
});
async function poll() {
  if (!sessionId) return;
  try { acceptState(await api(API + '/' + sessionId)); setConnection(true); }
  catch (error) { setConnection(false); notify('Physics connection lost. Reload to reconnect. ' + error.message, true); }
  setTimeout(poll, 160);
}
async function boot() {
  try {
    config = await api(API + '/config');
    if (!config.model_available) throw new Error(config.detail || 'Robot assets are unavailable.');
    $('#cosmos-availability').textContent = config.cosmos_enabled ? 'Connected' : 'Disabled';
    $('#cosmos-note').textContent = config.cosmos_enabled ? 'Only this robot-camera image is sent for inference.' : 'Disabled for this local launch. Pose previews are available; automatic spray stays off.';
    $('#cosmos-note').classList.toggle('warn', !config.cosmos_enabled);
    manifest = await api(API + '/model');
    const prior = sessionStorage.getItem('scene2real-live-session');
    let state;
    if (prior) { try { state = await api(API + '/' + prior); } catch { /* create a new session after restart */ } }
    if (!state) state = await api(API, {});
    sessionId = state.session_id; sessionStorage.setItem('scene2real-live-session', sessionId); acceptState(state);
    await initRenderer(); setConnection(true);
    notify(config.cosmos_enabled ? '' : 'Local physics preview · Cosmos is disabled · Automatic spray is off');
    renderUI(); poll();
    document.body.dataset.ready = 'true';
  } catch (error) {
    setConnection(false); notify(error.message, true);
    $('#scene-loading').textContent = 'Simulation unavailable. ' + error.message;
  }
}
boot();
