import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const inventory = JSON.parse(fs.readFileSync(path.join(project, '.prd-to-production/fire-reporting/research/historical-worksheet-fields.json'), 'utf8'));
const expected = inventory.sections.flatMap(section => section.questions);
const normalize = s => s.replace(/\s+/g, ' ').trim();
const worksheet = page => page.locator('#incident-sheet');

test.describe.configure({ mode: 'serial' });
test.beforeEach(async ({ page }) => page.on('pageerror', error => { throw error; }));

async function openReport(page, id) {
  await page.goto(`/?run=${id}#report`);
  await expect(page.getByRole('button', { name: 'Generate worksheet' })).toBeVisible();
}
async function generate(page) {
  await page.getByRole('button', { name: 'Generate worksheet' }).click();
  await expect(page.getByRole('article', { name: 'IRS WORKSHEET', exact: true })).toBeVisible();
}
const answer = (page, id) => worksheet(page).locator(`.irs-question[data-question-id="${id}"] .irs-answer`);
const field = (page, id) => answer(page, id).locator('textarea.irs-answer-input');
const expectStatus = (page, id, value) => expect(answer(page, id)).toHaveAttribute('data-status', value);
const REMOVED_COPY = [
  'Generate the IRS worksheet from this run.',
  'IRS worksheet. Any draft is machine-observed and unverified. Unsupported answers stay blank.',
  'Vision draft · unverified · Synthetic Scene2Real footage · V1:A1 · Yellow-orange flames rising from a low rectangular base on the left foreground floor.',
  'This worksheet reproduces the numbered question headings only. It does not reconstruct all subfields, options or validation rules.',
  'Generate the IRS worksheet from validated analysis. Unsupported answers stay blank.',
  'Edits stay in this browser and are cleared when the run changes.',
  'DEMO · SAMPLE CONTENT · NOT FOR INCIDENT SUBMISSION',
];
async function expectCopyRemoved(page) {
  const text = await page.locator('body').innerText();
  for (const copy of REMOVED_COPY) expect(text).not.toContain(copy);
  expect(text).not.toMatch(/synthetic/i);
  expect(text).not.toContain('Video evidence');
}
async function checkWorksheet(page) {
  const root = worksheet(page);
  const rows = root.locator('.irs-question');
  await expect(root.locator('.irs-section')).toHaveCount(9);
  await expect(rows).toHaveCount(158);
  const ids = await rows.evaluateAll(nodes => nodes.map(n => n.dataset.questionId));
  expect(ids).toEqual(expected.map(q => q.id));
  const boxes = await rows.evaluateAll(nodes => nodes.map(row => {
    const input = row.querySelector('.irs-answer textarea.irs-answer-input');
    const label = row.querySelector(`label[for="${input?.id}"]`);
    return { text: row.innerText, inputs: row.querySelectorAll('input, textarea, select').length, value: input?.value || '', disabled: !!input?.disabled, labelled: !!label, status: row.querySelector('.irs-answer')?.dataset.status || '', pills: row.querySelectorAll('.irs-answer-status').length, answerText: row.querySelector('.irs-answer')?.innerText || '' };
  }));
  const counts = {};
  for (let i = 0; i < expected.length; i++) {
    const box = boxes[i];
    expect(normalize(box.text)).toContain(normalize(expected[i].label));
    expect(box.inputs, `${expected[i].id} has exactly one editable control`).toBe(1);
    expect(box.value.trim(), `${expected[i].id} starts with a value`).not.toBe('');
    expect(box.disabled).toBe(false);
    expect(box.labelled, `${expected[i].id} textarea has a label`).toBe(true);
    expect(box.pills, `${expected[i].id} shows no status pill`).toBe(0);
    expect(box.answerText).not.toMatch(/\b(?:Suggested|Sample|Edited)\b/);
    expect(['Suggested', 'Sample']).toContain(box.status);
    counts[box.status] = (counts[box.status] || 0) + 1;
  }
  expect(counts.Sample).toBeGreaterThan(100);
  const sections = await root.locator('.irs-section').evaluateAll(nodes => nodes.map(n => n.dataset.sectionName));
  expect(sections).toEqual(inventory.sections.map(s => s.name));
  await expect(root.locator('h3')).toHaveText('IRS WORKSHEET');
  await expect(page.locator('#h7')).toHaveText('IRS WORKSHEET');
  await expect(page.locator('#page-description')).toHaveText('Review and edit answers before printing.');
  await expect(page.getByRole('link', { name: /7 IRS WORKSHEET/ })).toBeVisible();
  await expect(root.locator('.irs-demo-banner, .irs-demo-footer')).toHaveCount(0);
  await expect(page.locator('#report-note')).toBeHidden();
  await expect(root.locator('#irs-legend .irs-legend-item')).toHaveCount(0);
  await expect(root.locator('.irs-answer-status')).toHaveCount(0);
  await expect(root).not.toContainText('Historical reference worksheet — not current FaRDaP or a validated submission.');
  await expect(root).not.toContainText('v1-0p');
  await expect(root).not.toContainText('v1-0n');
  await expect(root.locator('.irs-evidence-annex')).toHaveCount(0);
  await expect(page.locator('#s7 #video-evidence')).toHaveCount(0);
  await expect(root).toContainText('Department for Communities and Local Government');
  await expectCopyRemoved(page);
  return counts;
}

test('retained flame evidence marks only 3.1 as Suggested; every other box is a Sample', async ({ page }) => {
  await openReport(page, 'r_report_ok');
  await generate(page);
  const counts = await checkWorksheet(page);
  expect(counts.Suggested).toBe(1);
  expect(counts.Sample).toBe(157);
  await expect(field(page, '3.1')).toHaveValue('Fire');
  await expectStatus(page, '3.1', 'Suggested');
  await expect(answer(page, '3.1')).toContainText('Run analysis · V1:A1');
  await expect(answer(page, '3.1')).not.toContainText('Vision draft');
  await expect(answer(page, '3.1')).not.toContainText('burning packaging beside the right rack');
  await expectStatus(page, '3.2', 'Sample');
  await expectStatus(page, '4.2k', 'Sample');
  await expect(field(page, '4.2k')).not.toHaveValue('');
});

test('answer boxes are keyboard editable and edits are kept in the preview', async ({ page }) => {
  await openReport(page, 'r_report_ok');
  await generate(page);
  await field(page, '1.1').focus();
  await page.keyboard.press('ControlOrMeta+A');
  await page.keyboard.type('FRS/2026/000777');
  await expect(field(page, '1.1')).toHaveValue('FRS/2026/000777');
  await expectStatus(page, '1.1', 'Edited');
  await page.keyboard.press('Tab');
  await expect(field(page, '1.2')).toBeFocused();
  await page.keyboard.type(' /Users/someone/private.mp4');
  await page.keyboard.press('Tab');
  await expect(field(page, '1.2')).toHaveValue(/\[redacted\]$/);
  await expect(field(page, '1.2')).not.toHaveValue(/\/Users\//);
  await page.getByRole('link', { name: /6 Metrics/ }).click();
  await page.getByRole('link', { name: /7 IRS WORKSHEET/ }).click();
  await expect(field(page, '1.1')).toHaveValue('FRS/2026/000777');
  await expectStatus(page, '1.1', 'Edited');
  await field(page, '1.1').fill('DEMO-2026-000123');
  await expectStatus(page, '1.1', 'Sample');
});

test('legacy single-view context and disabled review remain attributable', async ({ page }) => {
  await page.route('**/api/runs/r_report_partial', async route => {
    const response = await route.fetch();
    const run = await response.json();
    delete run.analysis.views;
    run.analysis.spatial_review = { status:'disabled', reason:'Unreviewed Cosmos observations', raw_response:'PRIVATE_RAW_OUTPUT' };
    run.observations.scene_description = 'Visible warehouse context from the selected run';
    await route.fulfill({ response, json:run });
  });
  await openReport(page, 'r_report_partial');
  await generate(page);
  await expectStatus(page, '3.1', 'Sample');
  await expect(field(page, '3.2')).toHaveValue('Warehouse');
  await expectStatus(page, '3.2', 'Suggested');
  await expect(answer(page, '3.2')).toContainText('Run analysis · scene description');
  await expect(worksheet(page)).not.toContainText('PRIVATE_RAW_OUTPUT');
  await expectStatus(page, '1.1', 'Sample');
});

test('unanalysed run cannot generate a worksheet', async ({ page }) => {
  await openReport(page, 'r_report_uploaded');
  await expect(page.getByRole('button', { name: 'Generate worksheet' })).toBeDisabled();
  await expect(worksheet(page)).toHaveCount(0);
});

test('reset and reconfirmation invalidate a generated worksheet and its edits', async ({ page }) => {
  await openReport(page, 'r_report_reset');
  await generate(page);
  await field(page, '1.1').fill('STALE-EDIT-1');
  await page.getByRole('link', { name: /5 Simulation/ }).click();
  await page.getByRole('button', { name: 'Reset' }).click();
  await expect(page.locator('#run-state')).toHaveAttribute('data-state', 'scene_ready');
  await expect(worksheet(page)).toHaveCount(0);
  await page.getByRole('link', { name: /7 IRS WORKSHEET/ }).click();
  await generate(page);
  await expect(field(page, '1.1')).not.toHaveValue('STALE-EDIT-1');
  await expectStatus(page, '1.1', 'Sample');
  await openReport(page, 'r_report_confirm');
  await generate(page);
  await field(page, '1.1').fill('STALE-EDIT-2');
  await page.getByRole('link', { name: /3 Confirm target/ }).click();
  await page.getByRole('button', { name: 'Confirm fires' }).click();
  await expect(page.locator('#run-state')).toHaveAttribute('data-state', 'confirmed');
  await expect(worksheet(page)).toHaveCount(0);
  await page.getByRole('link', { name: /7 IRS WORKSHEET/ }).click();
  await generate(page);
  await expect(field(page, '1.1')).not.toHaveValue('STALE-EDIT-2');
});

test('switching runs never reuses another run’s worksheet or edits', async ({ page }) => {
  await openReport(page, 'r_report_ok');
  await generate(page);
  await field(page, '1.1').fill('EDIT-FROM-FIRST-RUN');
  await openReport(page, 'r_report_fail');
  await expect(worksheet(page)).toHaveCount(0);
  await generate(page);
  await expect(field(page, '1.1')).not.toHaveValue('EDIT-FROM-FIRST-RUN');
  await expectStatus(page, '1.1', 'Sample');
  await expectStatus(page, '3.1', 'Suggested');
});

test('changed server snapshot prevents stale printing', async ({ page }) => {
  await openReport(page, 'r_report_ok');
  await generate(page);
  await page.evaluate(() => { window.__printCalled = false; window.print = () => { window.__printCalled = true; }; });
  await page.route('**/api/runs/r_report_ok', async route => {
    const response = await route.fetch();
    const run = await response.json();
    run.observations.fire_sources[0].description = 'Changed server observation';
    await route.fulfill({ response, json: run });
  });
  await page.getByRole('button', { name: 'Print / Save as PDF' }).click();
  await expect.poll(() => page.evaluate(() => window.__printCalled)).toBe(false);
  await expect(worksheet(page)).toHaveCount(0);
});

test('fresh snapshot prints and a failed freshness request never prints', async ({ page }) => {
  await openReport(page, 'r_report_ok');
  await generate(page);
  await page.evaluate(() => { window.__printCalled = false; window.print = () => { window.__printCalled = true; }; });
  await page.getByRole('button', { name: 'Print / Save as PDF' }).click();
  await expect.poll(() => page.evaluate(() => window.__printCalled)).toBe(true);
  await page.evaluate(() => { window.__printCalled = false; });
  await page.route('**/api/runs/r_report_ok', route => route.abort('failed'));
  await page.getByRole('button', { name: 'Print / Save as PDF' }).click();
  await expect(worksheet(page)).toHaveCount(0);
  expect(await page.evaluate(() => window.__printCalled)).toBe(false);
});

test('leaving a run during print verification never prints its stale worksheet', async ({ page }) => {
  await openReport(page, 'r_report_ok');
  await generate(page);
  let prints = 0, release, received;
  await page.exposeFunction('__markPrint', () => { prints++; });
  await page.evaluate(() => { window.print = () => window.__markPrint(); });
  const held = new Promise(resolve => { release = resolve; });
  const arrived = new Promise(resolve => { received = resolve; });
  await page.route('**/api/runs/r_report_ok', async route => {
    received();
    await held;
    try { await route.continue(); } catch { /* Navigation may cancel the request. */ }
  });
  try {
    await page.getByRole('button', { name: 'Print / Save as PDF' }).click();
    await arrived;
    await openReport(page, 'r_report_fail');
    await generate(page);
    release();
    await expect(worksheet(page)).toContainText('flame on the left pallet only');
    expect(prints).toBe(0);
  } finally { release(); }
});

test('late generation from an earlier run cannot replace the new run', async ({ page }) => {
  await openReport(page, 'r_report_ok');
  await expect(page.getByRole('button', { name: 'Generate worksheet' })).toBeEnabled();
  let release;
  const held = new Promise(resolve => { release = resolve; });
  let received;
  const arrived = new Promise(resolve => { received = resolve; });
  await page.route('**/api/runs/r_report_ok', async route => {
    received();
    await held;
    try { await route.continue(); } catch { /* Navigation may cancel the old request. */ }
  });
  try {
    await page.getByRole('button', { name: 'Generate worksheet' }).click();
    await arrived;
    await openReport(page, 'r_report_fail');
    await generate(page);
    await expect(worksheet(page)).toContainText('flame on the left pallet only');
    release();
    await expect(worksheet(page)).toContainText('flame on the left pallet only');
    await expect(worksheet(page)).not.toContainText('burning packaging beside the right rack');
    await expect(page).toHaveURL(/run=r_report_fail/);
  } finally { release(); }
});

test('native print without verification shows guard instead of report', async ({ page }) => {
  await openReport(page, 'r_report_ok');
  await generate(page);
  await page.emulateMedia({ media: 'print' });
  expect(await page.locator('html').evaluate(el => getComputedStyle(el).colorScheme)).toBe('light');
  await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
  await expect(page.locator('body')).not.toHaveClass(/irs-print-verified/);
  await expect(page.locator('#irs-print-guard')).toBeVisible();
  await expect(worksheet(page)).toBeHidden();
  await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
  await expect(page.locator('body')).not.toHaveClass(/irs-print-verified/);
});

test('all questions, statuses and edited values print across readable A4 pages', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openReport(page, 'r_report_ok');
  await generate(page);
  await field(page, '1.1').fill('PRINTED-EDIT-000777');
  await field(page, '4.2k').fill('Rear aisle, edited before printing /Users/someone/private.mp4');
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width + 1);
    const overflow = await worksheet(page).locator('.irs-question').evaluateAll(rows => rows.filter(row => row.scrollWidth > row.clientWidth + 1).length);
    expect(overflow).toBe(0);
  }
  await page.evaluate(() => { window.__printCalled = false; window.print = () => { window.__printCalled = true; }; });
  await page.getByRole('button', { name: 'Print / Save as PDF' }).click();
  await expect.poll(() => page.evaluate(() => window.__printCalled)).toBe(true);
  await expect(page.locator('body')).toHaveClass(/irs-print-verified/);
  await page.emulateMedia({ media: 'print' });
  const printInfo = await worksheet(page).evaluate(el => ({ background: getComputedStyle(el).backgroundColor, font: parseFloat(getComputedStyle(el).fontSize), overflow: el.scrollWidth > el.clientWidth + 1 }));
  expect(printInfo.background).toBe('rgb(255, 255, 255)');
  expect(printInfo.font).toBeGreaterThanOrEqual(13);
  expect(printInfo.overflow).toBe(false);
  await expect(field(page, '1.1')).toBeHidden();
  await expect(answer(page, '1.1').locator('.irs-answer-print')).toBeVisible();
  await expect(answer(page, '1.1').locator('.irs-answer-print')).toHaveText('PRINTED-EDIT-000777');
  await expect(worksheet(page).locator('.irs-demo-banner, .irs-demo-footer')).toHaveCount(0);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'irs-print-'));
  try {
    const file = path.join(dir, 'worksheet.pdf');
    await page.pdf({ path: file, format: 'A4', printBackground: true, preferCSSPageSize: true });
    const python = process.env.PDF_PYTHON || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3');
    const result = JSON.parse(execFileSync(python, ['-c', 'import json,sys; from pypdf import PdfReader; r=PdfReader(sys.argv[1]); print(json.dumps({"pages":len(r.pages),"text":"\\n".join(p.extract_text() or "" for p in r.pages)}))', file], { encoding: 'utf8' }));
    expect(result.pages).toBeGreaterThan(1);
    const text = normalize(result.text);
    for (const q of expected) expect(text, `PDF missing ${q.id} ${q.label}`).toContain(normalize(`${q.id} ${q.label}`));
    expect(text).not.toContain('Video evidence');
    expect(text).not.toContain('Historical reference worksheet — not current FaRDaP or a validated submission.');
    expect(text).toContain('IRS WORKSHEET');
    expect(text).not.toContain('v1-0p');
    expect(text).not.toContain('v1-0n');
    expect(text).toContain('PRINTED-EDIT-000777');
    expect(text).toContain('Rear aisle, edited before printing [redacted]');
    expect(text).not.toContain('/Users/');
    expect(text).not.toContain('DEMO · SAMPLE CONTENT · NOT FOR INCIDENT SUBMISSION');
    expect(text).not.toContain('Suggested');
    expect(text).not.toContain('Edited');
    expect(text).not.toContain('Edits stay in this browser and are cleared when the run changes.');
    expect(text).not.toContain('burning packaging beside the right rack');
    expect(text).not.toMatch(/synthetic/i);
    expect(text).not.toContain('Vision draft');
    expect(text).not.toContain('numbered question headings only');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('trailing negation and uncertain warehouse evidence are not Suggested', async ({ page }) => {
  await page.route('**/api/runs/r_report_ok', async route => {
    const response = await route.fetch();
    const run = await response.json();
    for (const source of run.observations.fire_sources) {
      source.description = 'Flames are not visible';
      source.burning_object = 'burnt residue';
      source.smoke_description = 'Flames may be a reflection';
    }
    run.observations.scene_description = 'warehouse cannot be confirmed';
    await route.fulfill({ response, json: run });
  });
  await openReport(page, 'r_report_ok');
  await generate(page);
  await expectStatus(page, '3.1', 'Sample');
  await expectStatus(page, '3.2', 'Sample');
  await expectStatus(page, '4.2k', 'Sample');
  await expect(worksheet(page).locator('.irs-answer[data-status="Suggested"]')).toHaveCount(1);
});

test('twelve sightings fit one A4 row without dumping every excerpt', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openReport(page, 'r_report_dense');
  await generate(page);
  await expect(field(page, '3.1')).toHaveValue('Fire');
  await expectStatus(page, '3.1', 'Suggested');
  await expect(answer(page, '3.1')).not.toContainText('position 12');
  await expectStatus(page, '3.2', 'Sample');
  await expectStatus(page, '4.2k', 'Sample');
  await page.evaluate(() => { window.__printCalled = false; window.print = () => { window.__printCalled = true; }; });
  await page.getByRole('button', { name: 'Print / Save as PDF' }).click();
  await expect.poll(() => page.evaluate(() => window.__printCalled)).toBe(true);
  await page.emulateMedia({ media: 'print' });
  const fit = await answer(page, '3.1').evaluate(node => {
    const row = node.closest('.irs-question');
    const pageContent = (297 - 24) * 96 / 25.4;
    return {
      rowHeight: row.getBoundingClientRect().height,
      pageContent,
      rowClipped: row.scrollHeight > row.clientHeight + 1 || row.scrollWidth > row.clientWidth + 1,
      answerClipped: node.scrollHeight > node.clientHeight + 1 || node.scrollWidth > node.clientWidth + 1,
    };
  });
  expect(fit.rowHeight).toBeGreaterThan(0);
  expect(fit.rowHeight).toBeLessThanOrEqual(fit.pageContent);
  expect(fit.rowClipped).toBe(false);
  expect(fit.answerClipped).toBe(false);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'irs-dense-print-'));
  try {
    const file = path.join(dir, 'dense.pdf');
    await page.pdf({ path: file, format: 'A4', printBackground: true, preferCSSPageSize: true });
    const python = process.env.PDF_PYTHON || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3');
    const result = JSON.parse(execFileSync(python, ['-c', 'import json,sys; from pypdf import PdfReader; r=PdfReader(sys.argv[1]); print(json.dumps({"pages":len(r.pages),"text":"\\n".join(p.extract_text() or "" for p in r.pages)}))', file], { encoding: 'utf8' }));
    const text = normalize(result.text);
    expect(result.pages).toBeGreaterThan(1);
    expect(text).toContain('Suggested');
    expect(text).not.toContain('aisle position 12');
    expect(text).not.toContain('Video evidence');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
