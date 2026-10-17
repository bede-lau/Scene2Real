const fs=require('fs'), vm=require('vm'), assert=require('assert');
const s=fs.readFileSync('static/app.js','utf8');
class E { constructor(t){this.tag=t;this.nodeType=1;this.children=[];this.dataset={};this.classList={toggle(){}};} setAttribute(k,v){this[k]=v} addEventListener(){} append(...x){this.children.push(...x)} replaceChildren(...x){this.children=x} }
const dom={};const $=x=>dom[x] ||=new E(x);const raw='```json\n{"cause":null,"unknowns":["cause","depth_m"]}\n```';
const obs={fire_sources:[],cause:null,scale:null,depth_m:null,unknowns:['cause','depth_m']};
const S={view:'V1',busy:null,run:{state:'completed',model_id:'cosmos',analysis:{views:[{view_id:'V1',analysis:{raw_text:raw,cached:true},observations:obs},{view_id:'V2',analysis:{raw_text:'live',cached:false},observations:obs}]},observations:obs,metrics:{success:false,rule:'all fires and zero collisions (scripted demo proxy)',target_count:1,suppressed_count:0,targets:[{target_id:'T1',suppressed:false,best_valid_exposure_s:0,suppressed_at_s:null,failure_reason:'No exposure'}]},timings_s:{},instruction:{text:'Go',source:'fallback',fallback_reason:'provider unavailable'},skill:{}}};
const ctx=vm.createContext({S,$,document:{createElement:t=>new E(t),createTextNode:s=>({nodeType:3,textContent:String(s)})},Number,String,JSON,Math,icon:()=>new E('icon'),drawSpark:()=>{}});
const helpers=s.slice(s.indexOf('function h('),s.indexOf('// ---------------- API'));
const cosmos=s.slice(s.indexOf('function activeFires()'),s.indexOf('function initGroups('));
const instr=s.slice(s.indexOf('function renderInstruction()'),s.indexOf('function renderSim()'));
const metrics=s.slice(s.indexOf('function renderMetrics()'),s.indexOf('function drawSpark('));
vm.runInContext(helpers+cosmos+instr+metrics+';renderCosmos();renderInstruction();renderMetrics()',ctx);
function text(n){return n.textContent||n.children?.map(text).join(' ')||''}function nodes(n){return [n,...(n.children||[]).flatMap(nodes)]}
const panels=nodes(dom['#cosmos-out']);assert(panels.some(n=>n.tag==='pre'&&text(n)===raw),'raw response verbatim');
const content=text(dom['#cosmos-out']);assert(content.includes('"depth_m": null'));assert(!nodes(dom['#cosmos-out']).some(n=>n.tag==='dt' && ['Cause','Scale','Depth','Unknowns'].includes(text(n))));
assert(text(dom['#cosmos-facts']).includes('cached'));assert(text(dom['#cosmos-facts']).includes('some cached'));
S.view='V2';vm.runInContext('renderCosmos()',ctx);assert(text(dom['#cosmos-facts']).includes('live'));assert(text(dom['#cosmos-facts']).includes('some cached'));
assert(!text(dom['#instr-out']).includes('Deterministic fallback'));assert(text(dom['#instr-out']).includes('provider unavailable'));
S.run.instruction={text:'Move safely',source:'openai',model_id:'gpt-6-astra',prompt_id:'mobile_plan_r1_v2'};vm.runInContext('renderInstruction()',ctx);
assert(text(dom['#instr-out']).includes('Move safely'));assert(!text(dom['#instr-out']).includes('gpt-6-astra'));assert(!text(dom['#instr-out']).includes('mobile_plan_r1_v2'));
const metricsText=text(dom['#metrics-out']);assert(metricsText.includes('FAIL'));assert(!metricsText.includes('all fires and zero collisions'));assert(!metricsText.includes('scripted demo proxy'));assert(!metricsText.includes('Failure reason'));assert(!metricsText.includes('No exposure'));
S.run.metrics.success=true;vm.runInContext('renderMetrics()',ctx);assert(text(dom['#metrics-out']).includes('PASS'));
assert(s.includes("st === 'completed' ? (r?.metrics?.success === true ? 'ok' : r?.metrics?.success === false ? 'bad' : '')"));
console.log('PASS: verbatim raw, full uncertainty, per-view cache, incident cache, fallback detail and verdict without projection rules');

// Effective boxes follow the nearest reviewed frame; old observations still use their static box.
const overlaySource=s.slice(s.indexOf('function boxAtTime('),s.indexOf('(function () {',s.indexOf('function boxAtTime(')));
const boxes=[];const ctx2d={setTransform(){},clearRect(){},fillRect(){},fillText(){},measureText(){return {width:35}},strokeRect(...x){boxes.push(x)},createLinearGradient(){return {addColorStop(){}}}};
const video={clientWidth:100,clientHeight:100,currentTime:0,readyState:0};
const canvas={width:0,height:0,style:{},getContext:()=>ctx2d};
const fire={id:'V1:A1',timestamps_s:[0,2],bbox_normalized:[.1,.1,.2,.2],bbox_at_s:0,bbox_provenance:{source:'openai',model_id:'gpt-6-astra',prompt_id:'spatial'},bbox_by_frame:[{t_s:0,bbox_normalized:[.1,.1,.2,.2]},{t_s:2,bbox_normalized:[.6,.6,.8,.8]}]};
const oc=vm.createContext({S:{view:'V1',run:{video_refs:[],clip_ref:{},analysis:{views:[{view_id:'V1',analysis:{spatial_review:{frame_times_s:[0,1,2]}}}]}}},$:x=>x==='#video'?video:canvas,activeFires:()=>[fire],devicePixelRatio:1,ACCENT:'#fff',ACCENT_2:'#fff',ACCENT_INK:'#000',Math,Number,Array});
vm.runInContext(overlaySource+';drawOverlay()',oc);assert(Math.abs(boxes[0][0]-10)<1e-6);
video.currentTime=2;vm.runInContext('drawOverlay()',oc);assert(Math.abs(boxes[1][0]-60)<1e-6);
video.currentTime=1;vm.runInContext('drawOverlay()',oc);assert.equal(boxes.length,2,'no overlay when nearest sampled frame lacks this source');
delete fire.bbox_by_frame;video.currentTime=0;vm.runInContext('drawOverlay()',oc);assert(Math.abs(boxes[2][0]-10)<1e-6);
fire.bbox_by_frame=[];vm.runInContext('drawOverlay()',oc);assert.equal(boxes.length,3,'reviewed empty series must not fall back to a static box');

// Raw Cosmos is preserved, and review metadata remains auditable.
S.view='V1';S.run.analysis.views[0].analysis.spatial_review={model_id:'gpt-6-astra',prompt_id:'spatial',status:'reviewed',raw_text:'raw spatial response',original_observations:{fire_sources:[{id:'F1'}]}};
S.run.analysis.views[0].observations={...obs,fire_sources:[fire]};S.run.observations={...obs,fire_sources:[fire]};
vm.runInContext('renderCosmos()',ctx);
assert(nodes(dom['#cosmos-out']).some(n=>n.tag==='pre'&&text(n)===raw));
for(const value of ['raw spatial response','original_observations','Astra reviewed','gpt-6-astra'])assert(text(dom['#cosmos-out']).includes(value),value);

// A manual matcher result and legacy Cosmos proposals never pre-group sightings.
S.run.state='analysed';S.run.run_id='incident';S.run.confirmed_target=null;S.run.observations.fire_sources=[{...fire,id:'V1:A1',view_id:'V1'},{...fire,id:'V2:A1',view_id:'V2'}];
S.run.observations.association_candidates=[{members:['V1:A1','V2:A1'],reason:'legacy suggestion'}];
S.run.analysis.association={status:'manual_review',room_status:'unverified',candidates:[],uncertainties:['No common landmark'],unmatched:[{id:'V1:A1',reason:'No correspondence'}],raw_text:'matcher raw'};
S.run.analysis.cosmos_association={candidates:[{members:['V1:A1','V2:A1']}],raw_text:'cosmos audit'};
S.groups=[];S.excluded={};S.zones={near:{slots:[[1,0,0],[2,0,0]]}};
ctx.STAGE_RETRY={};ctx.STATE_LABEL=x=>x;ctx.doConfirm=()=>{};
const confirm=s.slice(s.indexOf('function initGroups('),s.indexOf('function renderInstruction()'));
vm.runInContext(confirm+';renderConfirm()',ctx);
assert.equal(S.groups.length,2);assert(S.groups.every(g=>g.members.length===1));
for(const value of ['Cross-camera identity unverified.','No common landmark','No correspondence'])assert(text(dom['#confirm-out']).includes(value),value);
assert(!text(dom['#confirm-out']).includes('Cross-view matching unavailable.'));
assert(!text(dom['#confirm-out']).includes('cosmos audit'));
assert(!text(dom['#cosmos-out']).includes('visual evidence'));
assert.equal(vm.runInContext("displayClipName('Demo set 1 · West camera')",ctx),'Warehouse set 1 · West camera');
assert.equal(vm.runInContext("displayClipName('Demo set 1 · Center camera · Synthetic API-generated CCTV')",ctx),'Warehouse set 1 · Center camera');
assert.equal(vm.runInContext("displayClipName('Synthetic warehouse fire (OpenAI image + animation, 4 s)')",ctx),'Warehouse fire clip');
assert.equal(vm.runInContext("displayClipName('demo-set-2-east.mp4')",ctx),'warehouse-set-2-east.mp4');
assert.equal(vm.runInContext("displayClipName('other.mp4')",ctx),'other.mp4');
const html=fs.readFileSync('static/index.html','utf8');
assert(html.indexOf('id="chips-field"') > html.indexOf('id="s3"'));
assert(html.indexOf('id="chips-field"') < html.indexOf('id="s4"'));
assert(html.includes('Warehouse clips'));assert(html.includes('pages-g1-v1'));assert(html.includes('styles.css?v=pages-g1-v1'));
assert(!html.includes('id="sim-model-label"'));assert(!html.includes('id="recording"'));assert(!html.includes('recording-video'));assert(!html.includes('Scripted locomotion and water exposure proxy'));
const styles=fs.readFileSync('static/styles.css','utf8');
assert(styles.includes('#view-select,#sim-speed{appearance:none;padding-right:38px'));
assert(styles.includes('background-position:right 12px center'));
assert(fs.readFileSync('static/styles.css','utf8').includes('.facts .badge{display:inline-flex'));
S.run.confirmed_target={fire_id:'T1',zone:'near',members:['V1:A1'],association_provenance:'operator confirmed',position_provenance:'authored slot'};
vm.runInContext('renderConfirm()',ctx);assert(text(dom['#confirm-out']).includes('operator confirmed'));assert(text(dom['#confirm-out']).includes('authored slot'));
console.log('PASS: time-specific overlays, spatial audit, unverified matching, and confirmed provenance');

// Timestamp controls remain functional after moving to Confirm target.
const videoDom={};class VideoE extends E { constructor(t){super(t);this.events={}} addEventListener(k,v){this.events[k]=v} }
const videoElement=new VideoE('video');videoElement.pause=()=>{videoElement.paused=true};videoElement.scrollIntoView=()=>{videoElement.scrolled=true};
const selectElement=new VideoE('select');
const videoState={busy:null,clips:[{clip_id:'demo-set-1-west.mp4',label:'Demo set 1 · West camera'}],pending:[],uploadMsg:'',view:'V1',run:{run_id:'r1',clip_ref:{filename:'demo-set-1-west.mp4'},observations:{fire_sources:[{id:'F1',timestamps_s:[1.5]}]}}};
const video$=x=> x==='#video'?videoElement : x==='#view-select'?selectElement : (videoDom[x] ||=new VideoE(x));
const vc=vm.createContext({S:videoState,$:video$,document:{createElement:t=>new VideoE(t),createTextNode:s=>({nodeType:3,textContent:String(s)})},Number,String,JSON,Math,drawOverlay:()=>{}});
const renderVideoSrc=s.slice(s.indexOf('function renderVideo()'),s.indexOf('function renderCosmos()'));
vm.runInContext(helpers+renderVideoSrc+';renderVideo()',vc);
assert(text(videoDom['#clips']).includes('Warehouse set 1'));assert(text(selectElement).includes('warehouse-set-1-west.mp4'));
const chip=videoDom['#chips'].children[0];chip.events.click();assert.equal(videoElement.currentTime,1.5);assert(videoElement.paused);assert(videoElement.scrolled);
assert.equal(videoState.clips[0].clip_id,'demo-set-1-west.mp4');assert.equal(videoState.run.clip_ref.filename,'demo-set-1-west.mp4');
console.log('PASS: warehouse display labels preserve IDs and Confirm timestamp chip seeks its video');
