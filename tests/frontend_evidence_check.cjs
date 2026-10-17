const fs=require('fs'), vm=require('vm'), assert=require('assert');
const s=fs.readFileSync('static/app.js','utf8');
class E { constructor(t){this.tag=t;this.nodeType=1;this.children=[];this.dataset={};this.classList={toggle(){}};} setAttribute(k,v){this[k]=v} addEventListener(){} append(...x){this.children.push(...x)} replaceChildren(...x){this.children=x} }
const dom={};const $=x=>dom[x] ||=new E(x);const raw='```json\n{"cause":null,"unknowns":["cause","depth_m"]}\n```';
const obs={fire_sources:[],cause:null,scale:null,depth_m:null,unknowns:['cause','depth_m']};
const S={view:'V1',busy:null,run:{state:'completed',model_id:'cosmos',analysis:{views:[{view_id:'V1',analysis:{raw_text:raw,cached:true},observations:obs},{view_id:'V2',analysis:{raw_text:'live',cached:false},observations:obs}]},observations:obs,metrics:{success:false,rule:'all fires and zero collisions',target_count:1,suppressed_count:0},timings_s:{},instruction:{text:'Go',source:'fallback',fallback_reason:'provider unavailable'},skill:{}}};
const ctx=vm.createContext({S,$,document:{createElement:t=>new E(t),createTextNode:s=>({nodeType:3,textContent:String(s)})},Number,String,JSON,Math,icon:()=>new E('icon'),drawSpark:()=>{}});
const helpers=s.slice(s.indexOf('function h('),s.indexOf('// ---------------- API'));
const cosmos=s.slice(s.indexOf('function activeFires()'),s.indexOf('function initGroups('));
const instr=s.slice(s.indexOf('function renderInstruction()'),s.indexOf('function renderSim()'));
const metrics=s.slice(s.indexOf('function renderMetrics()'),s.indexOf('function drawSpark('));
vm.runInContext(helpers+cosmos+instr+metrics+';renderCosmos();renderInstruction();renderMetrics()',ctx);
function text(n){return n.textContent||n.children?.map(text).join(' ')||''}function nodes(n){return [n,...(n.children||[]).flatMap(nodes)]}
const panels=nodes(dom['#cosmos-out']);assert(panels.some(n=>n.tag==='pre'&&text(n)===raw),'raw response verbatim');
const content=text(dom['#cosmos-out']);assert(content.includes('"depth_m": null'));assert(content.includes('cause, depth_m'));assert(content.includes('Cause'));assert(content.includes('Depth'));
assert(text(dom['#cosmos-facts']).includes('cached'));assert(text(dom['#cosmos-facts']).includes('some cached'));
S.view='V2';vm.runInContext('renderCosmos()',ctx);assert(text(dom['#cosmos-facts']).includes('live'));assert(text(dom['#cosmos-facts']).includes('some cached'));
assert(text(dom['#instr-out']).includes('Deterministic fallback'));assert(text(dom['#instr-out']).includes('provider unavailable'));
assert(text(dom['#metrics-out']).includes('FAIL'));assert(text(dom['#metrics-out']).includes('all fires and zero collisions'));
S.run.metrics.success=true;vm.runInContext('renderMetrics()',ctx);assert(text(dom['#metrics-out']).includes('PASS'));
assert(s.includes("st === 'completed' ? (r?.metrics?.success === true ? 'ok' : r?.metrics?.success === false ? 'bad' : '')"));
console.log('PASS: verbatim raw, full uncertainty, per-view cache, incident cache, fallback provenance, verdict and rule');
