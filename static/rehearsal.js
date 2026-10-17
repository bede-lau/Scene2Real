import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const API = '/api/live';
let current, manifest, sessionId, scene, renderer, observerCamera, robotCamera, controls;
let meshes = [], fireGroup, flameMaterial, fireLight, sprayLine, sprayParticles, sparkPositions, cameraMode = 'observer';
let busy = false, renderingReady = false, previousWall = performance.now(), active = true, pausedForPage = false;
const meshCache = new Map();
const cap = value => value ? value[0].toUpperCase() + value.slice(1) : '—';
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {cache:'no-store'} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Physics request failed.');
  return result;
}
function notify(message = '') { const box=$('#notice'); box.textContent=message; box.hidden=!message; box.classList.toggle('error',!!message); }
function acceptState(state) {
  if (current && state.session_id === current.session_id && state.seq < current.seq) return;
  current=state; renderUI();
}
function renderUI() {
  if (!current) return;
  const state=current;
  $$('#scenarios button').forEach(button=>button.setAttribute('aria-pressed',button.dataset.scenario===state.scenario));
  $$('#pose-controls button').forEach(button=>button.setAttribute('aria-pressed',button.dataset.pose===state.pose));
  if (document.activeElement!==$('#fire-position')) {
    const y=state.fire.intensity>0 ? state.fire.position[1] : 0;
    $('#fire-position').value=y; $('#fire-position-value').textContent=y.toFixed(2)+' m';
  }
  $('#fire-position').disabled=state.scenario==='none'; $('#obstacle').checked=!!state.obstacle;
  $('#pause-button span').textContent=state.paused?'Resume physics':'Pause physics';
  $('#pause-button').setAttribute('aria-pressed',state.paused);
  $('#sim-clock').textContent=Math.floor(state.sim_time/60).toString().padStart(2,'0')+':'+(state.sim_time%60).toFixed(2).padStart(5,'0');
  $('#motion-label').textContent='Predefined motion · '+cap(state.pose)+(state.scenario==='wrong'?' · Wrong aim override':'');
}
async function command(endpoint, body) {
  if (!sessionId||busy) return;
  busy=true;
  try { acceptState(await api(API+'/'+sessionId+'/'+endpoint,body)); notify(); }
  catch(error) { notify(error.message); }
  finally { busy=false; }
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
  const host = $('#observer'), w = Math.max(1, host.clientWidth), h = Math.max(1, host.clientHeight);
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

  }
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

async function poll() {
  if (sessionId && active) {
    try { acceptState(await api(API+'/'+sessionId)); }
    catch(error) { notify('Physics connection lost. Reload this page to reconnect. '+error.message); }
  }
  setTimeout(poll,active?160:700);
}
function reportSize() { parent.postMessage({type:'scene2real-rehearsal-resize',height:document.body.scrollHeight},location.origin); }
new ResizeObserver(reportSize).observe(document.body);
addEventListener('message',async event=>{
  if(event.origin!==location.origin||event.source!==parent||event.data?.type!=='scene2real-page') return;
  active=!!event.data.active;
  if(!sessionId||!current) return;
  if(!active&&!current.paused) { pausedForPage=true; await command('control',{action:'pause'}); }
  else if(active&&pausedForPage) { pausedForPage=false; await command('control',{action:'resume'}); }
});
async function boot() {
  try {
    const config=await api(API+'/config');
    if(!config.model_available) throw new Error(config.detail||'Robot assets are unavailable.');
    manifest=await api(API+'/model');
    let state;
    const saved=sessionStorage.getItem('scene2real-embedded-g1');
    if(saved) { try{state=await api(API+'/'+saved);}catch{} }
    if(!state) state=await api(API,{});
    sessionId=state.session_id;
    const scenario=new URLSearchParams(location.search).get('scenario');
    if(['left','center','right'].includes(scenario)) state=await api(API+'/'+sessionId+'/scene',{scenario});
    sessionStorage.setItem('scene2real-embedded-g1',sessionId); acceptState(state);
    await initRenderer(); document.body.dataset.ready='true'; poll(); reportSize();
  } catch(error) { notify(error.message); $('#scene-loading').textContent='Simulation unavailable. '+error.message; }
}
boot();
