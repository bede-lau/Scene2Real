// Historical IRS worksheet. Run-supported drafts are limited to 3.1 and 3.2; every other
// answer carries a deterministic illustrative sample. All answers are editable client-side.
import { IRS_2012_WORKSHEET } from './irs_2012_worksheet.js';

const SENSITIVE = /(?:s3:\/\/\S+|https?:\/\/\S+|file:\/\/\S+|Bearer\s+\S+|sk-[A-Za-z0-9_-]+|(?:api[_-]?key|secret|token|password)\s*[:=]\s*\S+)/gi;
export function scrub(value) {
  if (value == null) return null;
  return String(value)
    // Quoted paths may contain spaces. Redact the whole quoted value before
    // processing unquoted paths, so a suffix cannot survive redaction.
    .replace(/(["'])(?:file:\/\/|~\/|\/{1,2}|[A-Za-z]:\\|\\\\|\.{1,2}\/|(?:config|runs)\/)[^\n"']*\1/gi, '[redacted]')
    // Known local roots can contain spaces; conservatively remove the rest of
    // that clause when there is no reliable way to locate the path's end.
    .replace(/(^|[\s(\[=:])(?:file:\/\/|~\/|\/(?:Users|home|var|tmp|private|config|opt|Volumes)\/)[^\n,;]*/gi, '$1[redacted]')
    .replace(SENSITIVE, '[redacted]')
    .replace(/(^|[\s(\[=:])(?:config|runs)\/[^\s<>"']+/gi, '$1[redacted]')
    .replace(/(^|[\s(\[=:])\/\/[^\s<>"']+/g, '$1[redacted]')
    .replace(/(?:[A-Za-z]:\\|\\\\)[^\s<>\"']+/g, '[redacted]')
    .replace(/(^|[\s(\[=:])(?:\.{1,2}\/)+(?:[^\s<>\"']+)/g, '$1[redacted]')
    .replace(/(^|[\s(\[=:])\/(?:[^\s\/<>\"']+\/)+[^\s<>\"']*/g, '$1[redacted]')
    .trim() || null;
}
export function analysisReady(run) {
  return !!(run && run.state !== 'uploaded' && run.state !== 'needs_review' &&
    !(run.state === 'failed' && run.error?.stage === 'analyse') && run.analysis &&
    typeof run.analysis === 'object' && Array.isArray(run.observations?.fire_sources));
}
function safeFilename(name) {
  if (typeof name !== 'string' || !name.trim() || /^(?:s3:|https?:)/i.test(name) || /X-Amz-|Signature=/i.test(name)) return null;
  return scrub(name.split(/[\\/]/).pop());
}
function reviewProvenance(review) {
  if (!review || typeof review !== 'object') return null;
  return { status:scrub(review.status), source:scrub(review.source), model:scrub(review.model_id), prompt:scrub(review.prompt_id), reason:scrub(review.reason) };
}
function cleanRef(ref) {
  if (!ref || typeof ref !== 'object') return null;
  return { view: scrub(ref.view_id), filename: safeFilename(ref.filename), kind: scrub(ref.kind),
    label: scrub(ref.label), sha256: typeof ref.sha256 === 'string' ? ref.sha256 : null };
}
// Includes every rendered source/provenance and observation as well as invalidating transitions.
export function fingerprint(run) {
  if (!run || typeof run !== 'object') return '';
  return JSON.stringify({run_id: run.run_id, state: run.state, error: run.error,
    clip_ref: cleanRef(run.clip_ref), video_refs: (run.video_refs || []).map(cleanRef),
    model_id: run.model_id, prompt_id: run.prompt_id,
    cached: run.analysis?.cached, spatial_review:reviewProvenance(run.analysis?.spatial_review), views: (run.analysis?.views || []).map(v => ({view_id:v?.view_id, state:v?.state, cached:v?.analysis?.cached, model_id:v?.analysis?.model_id, prompt_id:v?.analysis?.prompt_id, spatial_review:reviewProvenance(v?.analysis?.spatial_review)})),
    observations: run.observations, excluded: run.excluded,
    confirmed_target: run.confirmed_target, confirmed_targets: run.confirmed_targets,
    instruction: run.instruction, skill: run.skill, metrics: run.metrics});
}
export function retainReport(snapshot, run, action) {
  if (!snapshot || ['analyse','confirm','reset'].includes(action) || !run ||
      snapshot.report?.runId !== run.run_id || fingerprint(run) !== snapshot.fingerprint) return null;
  return snapshot;
}
function cacheLabel(run) {
  const views = run.analysis?.views || [];
  const flags = views.length ? views.map(v => v?.analysis?.cached) : [run.analysis?.cached];
  return flags.some(v => typeof v !== 'boolean') ? 'Cache status unknown' : flags.every(Boolean) ? 'Cached' : flags.some(Boolean) ? 'Some cached' : 'Not cached';
}
function freeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}
const FLAME_OR_BURNING = String.raw`\b(?:flames?|flaming|burning)\b`;
const WAREHOUSE_WORD = String.raw`\bwarehouses?\b`;
const NEGATION = String.raw`\b(?:no|not|non|never|without|none|absent|isn't|isnt|aren't|arent|wasn't|wasnt|weren't|werent|cannot|can't|cant|don't|dont|doesn't|doesnt)\b`;
const HEDGE = String.raw`\b(?:possible|possibly|maybe|perhaps|uncertain|unclear|unconfirmed|appears?|appearing|might|may|could|suspected|potentially|likely|unlikely|probably|suggests?|seems?|seeming|apparent)\b`;
const VISION_FIELDS = ['description', 'burning_object', 'smoke_description'];
function clauseHas(text, pattern) {
  if (typeof text !== 'string' || !text.trim()) return false;
  const re = new RegExp(pattern, 'gi');
  const neg = new RegExp(NEGATION, 'i');
  const hedge = new RegExp(HEDGE, 'i');
  let match;
  while ((match = re.exec(text))) {
    let before = text.slice(Math.max(0, match.index - 80), match.index);
    const butAt = before.toLowerCase().lastIndexOf(' but ');
    if (butAt >= 0 && neg.test(before.slice(0, butAt))) before = before.slice(butAt + 1);
    const tail = before.slice(-60);
    const after = text.slice(match.index + match[0].length, match.index + match[0].length + 80).split(/[.;\n]/)[0];
    if (neg.test(tail) || hedge.test(tail) || neg.test(after) || hedge.test(after)) continue;
    return true;
  }
  return false;
}
function excludedIds(run) {
  if (!Array.isArray(run?.excluded)) return new Set();
  const ids = [];
  for (const item of run.excluded) if (item && item.id != null) ids.push(item.id);
  return new Set(ids);
}
function retainedSources(run) {
  const excluded = excludedIds(run);
  const sources = run?.observations?.fire_sources;
  if (!Array.isArray(sources)) return [];
  return sources.filter(source => source && typeof source === 'object' && !excluded.has(source.id));
}
function sightingGroups(run, sources) {
  const byId = new Map();
  for (const source of sources) if (source.id != null && !byId.has(source.id)) byId.set(source.id, source);
  const seen = new Set();
  const groups = [];
  if (Array.isArray(run?.confirmed_targets)) {
    for (const target of run.confirmed_targets) {
      const members = Array.isArray(target?.members) ? target.members.filter(id => byId.has(id)) : [];
      if (!members.length) continue;
      for (const id of members) seen.add(id);
      groups.push(members.map(id => byId.get(id)));
    }
  }
  for (const source of sources) {
    if (source.id == null || seen.has(source.id)) continue;
    seen.add(source.id);
    groups.push([source]);
  }
  return groups;
}
function evidenceExcerpt(value) {
  const cleaned = scrub(value);
  if (!cleaned) return null;
  return cleaned.length > 96 ? cleaned.slice(0, 96).trim() + '…' : cleaned;
}
function flameCitations(run) {
  for (const group of sightingGroups(run, retainedSources(run))) {
    for (const source of group) {
      const field = VISION_FIELDS.find(name => clauseHas(source?.[name], FLAME_OR_BURNING));
      if (!field) continue;
      return [{ id: scrub(source.id) || 'unidentified', field, viewId: typeof source.view_id === 'string' ? source.view_id : null, excerpt: evidenceExcerpt(source[field]) }];
    }
  }
  return [];
}
function flameNote(citation) {
  const parts = ['Run analysis', citation.id];
  if (citation.field && citation.field !== 'description') parts.push(citation.field.replace(/_/g, ' '));
  return parts.join(' · ');
}
function suggestedAnswers(run) {
  const answers = {};
  const flames = flameCitations(run || {});
  if (flames.length) answers['3.1'] = { value: 'Fire', status: 'Suggested', note: flameNote(flames[0]) };
  const scene = run?.observations?.scene_description;
  if (clauseHas(scene, WAREHOUSE_WORD)) answers['3.2'] = { value: 'Warehouse', status: 'Suggested', note: 'Run analysis · scene description' };
  return answers;
}
// Illustrative values only. Plain words, never official option codes or hierarchy codes.
const SAMPLE_VALUES = Object.freeze({
  '1.1': 'DEMO-2026-000123', '1.2': 'Sample Fire and Rescue Service', '1.3': 'Sample station 07', '1.4': 'DEMO-OFFICER-42',
  '1.5': 'No', '1.6': 'Sample Fire and Rescue Service', '1.7': 'Not applicable',
  '2.1': '17 Oct 2026, 09:42', '2.2': 'Person (mobile telephone)', '2.3': 'Fire in a commercial building', '2.4': 'No',
  '2.5': '17 Oct 2026, 10:31', '2.6': '17 Oct 2026, 11:05',
  '3.1': 'Fire', '3.2': 'Warehouse', '3.3': 'Not applicable', '3.4': 'Not applicable', '3.5': 'None', '3.6': 'Evacuated without FRS assistance',
  '3.7': '2', '3.8': 'No', '3.9': 'No', '3.10': 'No', '3.11': 'Not applicable', '3.12': '0', '3.13': '0',
  '4.1': 'Yes', '4.2*': '1 Sample Way, Demo Trading Estate, Sampletown, DM1 2AB', '4.2k': 'Rear storage aisle of a single-storey unit', '4.3a/b': '400000 / 300000',
  '5.1': 'No', '5.2': 'Under 5 minutes', '5.3': 'Under 5 minutes', '5.4': 'Discovered by a person on site', '5.5': 'Yes', '5.6': 'Not affected',
  '5.7': 'Fire confined to compartment of origin', '5.8': 'Yes', '5.9': 'Smoke detection', '5.10': 'Throughout the premises', '5.11': 'Yes', '5.12': 'Not applicable',
  '5.13': 'Yes', '5.14': 'Yes', '5.15': 'Accidental', '5.16': '3', '5.16a': 'Not applicable', '5.17': 'Not applicable', '5.18': 'No', '5.19': 'None',
  '5.20': 'Not applicable', '5.21': 'Not applicable', '5.22': 'No', '5.23': '0', '5.24': '0', '5.25': '0', '5.26': 'No', '5.27': 'Not applicable',
  '5.28': 'Not applicable', '5.29': 'Not applicable', '5.30': 'Not applicable',
  '6.1': '1', '6.2': 'Pumping appliance', '6.3': 'DEMO-P1', '6.4': '5', '6.5': 'No', '6.6': '09:43', '6.7': '09:44', '6.8': '09:51', '6.9': '10:40',
  '6.10': 'Home station', '6.11': 'Sample station 07', '6.12': 'Yes', '6.13': 'Sample Fire Station, Station Road, Sampletown, DM1 3CD', '6.14a & b': '400100 / 300200',
  '6.15': 'Yes', '6.16': 'Hose reel', '6.17': '1',
  '7.1': 'No', '7.2': 'Called the fire service', '7.3': 'Extinguished the fire', '7.4': 'Yes', '7.5': 'Hose reel', '7.6': 'Extinguished the fire',
  '7.7': 'Yes', '7.8': 'Hose reels', '7.9': 'No', '7.10': 'Not applicable', '7.11': 'Yes', '7.12': 'Smoke alarm', '7.13': 'Same room as the fire',
  '7.14': 'Yes', '7.15': '1', '7.16': 'Alerted occupants', '7.17': 'Not applicable',
  '8.1': 'Accidental', '8.2': 'Not known', '8.3': 'Not known', '8.4': 'Not known', '8.5': 'Not known', '8.6': 'Packaging material', '8.7': 'Packaging material',
  '8.8': 'None', '8.9': 'None', '8.10': 'No', '8.11': 'Not applicable', '8.12': 'Not applicable', '8.13': 'No', '8.14': 'Storage area', '8.15': 'Not applicable',
  '8.16': 'None identified', '8.17': 'No', '8.18': 'No', '8.19': 'No', '8.20': 'Limited to the item first ignited', '8.21': 'Not applicable',
  '8.22': 'Limited to the item first ignited', '8.23': 'Not applicable', '8.24': '3', '8.25': '6', '8.26': '400', '8.27': '400', '8.28': '0', '8.29': '0',
  '8.30': 'Ground floor', '8.31': 'Not applicable', '8.32': 'Not applicable', '8.33': 'Not applicable', '8.34': 'Not applicable', '8.35': 'Not applicable',
  '8.35a': 'Not applicable', '8.36': 'No',
  '9.1': '4', '9.2': '0', '9.3': '0', '9.4': 'None', '9.5': 'Under 5 minutes', '9.6': 'No harm', '9.7': 'Not applicable', '9.8': 'Not applicable',
  '9.9': 'Not applicable', '9.10': 'Not applicable', '9.11': 'Not applicable', '9.12': 'Not applicable', '9.13': 'No', '9.14': 'Not applicable',
  '9.15': 'Not applicable', '9.16': 'Not applicable', '9.17': 'Not applicable', '9.18': 'Not applicable', '9.19': 'Not applicable',
  '9.20': 'Not applicable', '9.21': 'Not applicable', '9.22': 'Not applicable', '9.23': 'Not applicable', '9.24': 'Not applicable', '9.25': 'Not applicable', '9.26': 'No',
});
export function sampleAnswer(question) {
  const value = SAMPLE_VALUES[question.id];
  if (value) return { value, status: 'Sample', note: null };
  const label = String(question.label || '');
  if (/^(?:was|were|did|is|has|do|does)\b/i.test(label)) return { value: 'No', status: 'Sample', note: null };
  if (/^(?:how many|number)\b/i.test(label)) return { value: '0', status: 'Sample', note: null };
  return { value: 'Not applicable', status: 'Sample', note: null };
}
export function initialAnswers(run) {
  const suggested = suggestedAnswers(run);
  const answers = {};
  for (const group of IRS_2012_WORKSHEET.sections) for (const q of group.questions) answers[q.id] = suggested[q.id] || sampleAnswer(q);
  return answers;
}
export function buildReport(run, generatedAt) {
  const refs = (Array.isArray(run?.video_refs) && run.video_refs.length ? run.video_refs : [run?.clip_ref]).map(cleanRef).filter(Boolean);
  return freeze({runId:scrub(run?.run_id), generatedAt:generatedAt || '', refs, cache:cacheLabel(run || {}),
    model:scrub(run?.model_id), prompt:scrub(run?.prompt_id), scene:typeof run?.observations?.scene_description === 'string' ? scrub(run.observations.scene_description) : null, review:reviewProvenance(run?.analysis?.spatial_review), views:(run?.analysis?.views || []).map(v => ({id:scrub(v?.view_id), model:scrub(v?.analysis?.model_id), prompt:scrub(v?.analysis?.prompt_id), cached:typeof v?.analysis?.cached === 'boolean' ? (v.analysis.cached ? 'Cached' : 'Not cached') : 'Cache status unknown', review:reviewProvenance(v?.analysis?.spatial_review)})), answers:initialAnswers(run)});
}
export const MAX_EDIT_LENGTH = 2000;
// Operator edits live only in the browser, next to the immutable snapshot they belong to.
export function sanitizeEdit(value) {
  if (value == null) return '';
  const text = String(value).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '').replace(/\r\n?/g, '\n').slice(0, MAX_EDIT_LENGTH);
  return text.trim() ? (scrub(text) || '') : '';
}
export function effectiveAnswer(snapshot, id) {
  const base = snapshot?.report?.answers?.[id] || { value: '', status: 'Sample', note: null };
  const edits = snapshot?.edits;
  if (edits && Object.prototype.hasOwnProperty.call(edits, id)) return { value: edits[id], status: 'Edited', note: null };
  return base;
}
export function applyEdit(snapshot, id, value) {
  if (!snapshot || !snapshot.report?.answers || !Object.prototype.hasOwnProperty.call(snapshot.report.answers, id)) return null;
  if (!snapshot.edits || typeof snapshot.edits !== 'object') snapshot.edits = {};
  const clean = sanitizeEdit(value);
  if (clean === snapshot.report.answers[id].value) delete snapshot.edits[id];
  else snapshot.edits[id] = clean;
  return effectiveAnswer(snapshot, id);
}
function el(doc, tag, cls, text) {
  const node = doc.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
}
function addLine(doc, parent, label, value) {
  if (!value) return;
  const line = el(doc, 'p', 'irs-evidence-line');
  line.append(el(doc, 'strong', null, label + ': '), el(doc, 'span', null, value));
  parent.append(line);
}
const answerDomId = id => 'irs-answer-' + String(id).replace(/[^A-Za-z0-9]+/g, '-');
export function renderIncidentReport(doc, report, options = {}) {
  const snapshot = { report, edits: options.edits && typeof options.edits === 'object' ? options.edits : {} };
  const onEdit = typeof options.onEdit === 'function' ? options.onEdit : null;
  const sheet = el(doc, 'article', 'incident-sheet');
  sheet.id = 'incident-sheet';
  sheet.setAttribute('aria-label', 'IRS WORKSHEET');
  const head = el(doc, 'header', 'incident-head');
  head.append(el(doc, 'h3', null, 'IRS WORKSHEET'));
  head.append(el(doc, 'p', null, 'Department for Communities and Local Government, Incident Recording System – Questions and Lists from April 2012, Version 1.6, published July 2012. © Crown copyright 2012; Open Government Licence, excluding logos.'));
  head.append(el(doc, 'p', null, 'Source PDF SHA-256: ' + IRS_2012_WORKSHEET.source.pdf_sha256));
  let time = report.generatedAt;
  try { const date = new Date(time); if (Number.isFinite(date.getTime())) time = new Intl.DateTimeFormat('en-GB', {dateStyle:'medium',timeStyle:'short',timeZone:'Europe/London'}).format(date); } catch {}
  addLine(doc, head, 'Worksheet generation time', scrub(time));
  sheet.append(head);
  for (const group of IRS_2012_WORKSHEET.sections) {
    const section = el(doc, 'section', 'irs-section');
    section.setAttribute('data-section-name', group.name);
    section.append(el(doc, 'h4', null, group.name));
    for (const q of group.questions) {
      const row = el(doc, 'div', 'irs-question');
      row.setAttribute('data-question-id', q.id);
      const question = el(doc, 'div', 'irs-question-label');
      const label = el(doc, 'label', null);
      label.setAttribute('for', answerDomId(q.id));
      label.append(el(doc, 'strong', 'irs-question-id', q.id), doc.createTextNode(' ' + q.label + ' '));
      question.append(label, el(doc, 'span', 'irs-source-page', `p. ${q.source_page.printed}`));
      const answer = el(doc, 'div', 'irs-answer');
      answer.setAttribute('role', 'group'); answer.setAttribute('aria-label', 'Answer ' + q.id);
      const current = effectiveAnswer(snapshot, q.id);
      const input = el(doc, 'textarea', 'irs-answer-input');
      input.id = answerDomId(q.id);
      input.setAttribute('rows', '1');
      input.setAttribute('maxlength', String(MAX_EDIT_LENGTH));
      input.setAttribute('aria-label', 'Answer ' + q.id);
      input.value = current.value;
      input.textContent = current.value;
      const printed = el(doc, 'div', 'irs-answer-print', current.value);
      printed.setAttribute('aria-hidden', 'true');
      const update = next => {
        if (!next) return;
        printed.textContent = next.value;
        for (const node of [answer, input]) node.setAttribute('data-status', next.status);
      };
      if (typeof input.addEventListener === 'function') {
        input.addEventListener('input', () => update(onEdit ? onEdit(q.id, input.value) : applyEdit(snapshot, q.id, input.value)));
        input.addEventListener('change', () => { const next = effectiveAnswer(snapshot, q.id); if (input.value !== next.value) input.value = next.value; update(next); });
      }
      update(current);
      answer.append(input, printed);
      row.append(question, answer); section.append(row);
    }
    sheet.append(section);
  }
  return sheet;
}
