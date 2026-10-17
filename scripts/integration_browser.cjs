/* Actual merged-app browser acceptance. No model replies or HTTP routes are mocked.
 * PLAYWRIGHT_MODULE=/path/to/playwright node scripts/integration_browser.cjs
 * BASE_URL=http://127.0.0.1:8094 OUT=output/integration-browser
 * LIVE_COSMOS=1 explicitly authorizes exactly two camera inference requests.
 */
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.BASE_URL||'http://127.0.0.1:8094';
const out=process.env.OUT||'output/integration-browser';fs.mkdirSync(out,{recursive:true});
const checks=[],errors=[],failedAssets=[];
function check(name,condition,details={}){checks.push({name,passed:!!condition,...details});console.log(condition?'PASS':'FAIL',name);}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox','--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 const page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()>=400)failedAssets.push({url:r.url(),status:r.status()});});
 try{
  await page.goto(base,{waitUntil:'networkidle'});
  check('main workbench is default',await page.locator('#btn-analyse').count()===1);
  check('workbench navigation to live',await page.locator('a[href="/live.html"]').count()>0);
  await page.screenshot({path:path.join(out,'workbench-desktop.png'),fullPage:true});
  // Real upload/ingest, using an existing authorized repository fixture.
  const clip=fs.readdirSync('clips').find(f=>f.endsWith('.mp4'));
  if(clip){
   await page.locator('#file').setInputFiles(process.env.FIXTURE_WORKFLOW==='1'?[path.resolve('clips',clip),path.resolve('clips',clip)]:path.resolve('clips',clip));
   await page.locator('#btn-load').click();
   await page.waitForFunction(()=>document.querySelector('#run-id').textContent.startsWith('r_'),{timeout:30000});
   check('actual video upload creates incident',true,{clip,run_id:await page.locator('#run-id').innerText()});
   if(process.env.FIXTURE_WORKFLOW==='1'){
    const rid=await page.locator('#run-id').innerText();
    const analysed=page.waitForResponse(r=>r.url().endsWith('/analyse')&&r.request().method()==='POST');
    await page.locator('#btn-analyse').click();const analysis=await (await analysed).json();
    check('mocked perception enters real two-view workbench',analysis.state==='analysed'&&analysis.analysis.views.length===2&&analysis.analysis.views.every(v=>v.analysis.mocked));
    await page.getByLabel('Physical fire group for V2:F1',{exact:true}).selectOption('0');
    for(const id of ['V1:F2','V2:F2']){
     await page.getByLabel('Physical fire group for '+id,{exact:true}).selectOption('exclude');
     await page.getByLabel('Reason for excluding '+id,{exact:true}).fill('Mock fixture reflection; explicit operator test exclusion');
    }
    await page.getByLabel('Zone for fire 1',{exact:true}).selectOption('left_rack');
    await page.getByLabel('Slot for fire 1',{exact:true}).selectOption('0');
    await page.locator('#btn-confirm').click();
    await page.waitForFunction(()=>!document.querySelector('#btn-scene').disabled);
    const confirmed=await (await context.request.get(base+'/api/runs/'+rid)).json();
    check('real grouped confirmation preserves all sightings and exclusions',confirmed.confirmed_targets.length===1&&confirmed.confirmed_targets[0].members.length===2&&confirmed.excluded.length===2);
    await page.locator('#btn-scene').click();
    await page.waitForFunction(()=>!document.querySelector('#btn-run').disabled,{timeout:30000});
    await page.locator('#btn-run').click();
    await page.waitForFunction(()=>document.querySelector('#metrics-out').textContent.includes('PASS'),{timeout:120000});
    const completed=await (await context.request.get(base+'/api/runs/'+rid)).json();
    check('mocked planner with actual MuJoCo suppression succeeds',completed.metrics.success&&completed.instruction.source==='mocked');
    fs.writeFileSync(path.join(out,'mocked-services-real-physics-run.json'),JSON.stringify(completed,null,2));
    await page.locator('#btn-replay').click();
    await page.locator('#sim-speed').selectOption('2');
    const video=await context.request.get(base+'/api/runs/'+rid+'/simulation-video');
    check('actual Python simulation recording export',video.ok()&&(await video.body()).length>1000);
    fs.writeFileSync(path.join(out,'mocked-services-real-physics.mp4'),await video.body());
    await page.screenshot({path:path.join(out,'mocked-workbench-completed.png'),fullPage:true});
   }
  }else check('actual video upload creates incident',false,{reason:'No repository MP4 fixture available'});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'workbench-mobile.png'),fullPage:true});
  check('responsive workbench no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(base+'/legacy.html',{waitUntil:'networkidle'});await page.waitForURL(base+'/');
  check('legacy redirects to current workbench',page.url()===base+'/');
  await page.goto(base+'/live.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#connection-label').textContent.includes('connected'),{timeout:60000});
  await page.waitForFunction(()=>document.querySelectorAll('canvas').length>=2,{timeout:60000});
  await page.waitForTimeout(1000);
  check('live reciprocal navigation',await page.locator('a[href="/"]').count()>0);
  const config=await (await context.request.get(base+'/api/live/config')).json();
  check('G1 model available',config.model_available,{detail:config.detail});
  await page.screenshot({path:path.join(out,'live-observer-desktop.png'),fullPage:true});
  const evidenceLink=await page.locator('#evidence-download').getAttribute('href').catch(()=>null);
  let sid;
  const response=await page.waitForResponse(r=>/\/api\/live\/[a-f0-9]+$/.test(r.url())&&r.request().method()==='GET');
  const state=await response.json();sid=state.session_id;
  check('manual preview starts spray off',!state.spray.on);
  await page.locator('#robot-view').click();await page.waitForTimeout(300);
  await page.screenshot({path:path.join(out,'live-robot-camera.png'),fullPage:true});
  await page.locator('#observer-view').click();
  await page.locator('[data-pose="left"]').click();await page.waitForTimeout(500);
  let after=await (await context.request.get(base+'/api/live/'+sid)).json();
  check('manual pose cannot authorize spray',!after.spray.on&&after.decision.status!=='ready');
  await page.locator('#save-frame').click();await page.waitForTimeout(400);
  const evidence=await (await context.request.get(base+'/api/live/'+sid+'/evidence')).json();
  fs.writeFileSync(path.join(out,'manual-session-evidence.json'),JSON.stringify(evidence,null,2));
  check('robot snapshot persisted',evidence.files.some(f=>f.name.endsWith('.jpg')));
  await page.locator('#pause-button').click();await page.waitForTimeout(250);
  after=await (await context.request.get(base+'/api/live/'+sid)).json();check('pause revokes spray',after.paused&&!after.spray.on);
  await page.locator('#pause-button').click();
  await page.locator('#record-button').click();await page.waitForTimeout(2400);await page.locator('#record-button').click();
  await page.waitForFunction(()=>!document.querySelector('#video-download').hidden,{timeout:15000});
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#video-download').click()]);
  await download.saveAs(path.join(out,'actual-merged-manual-preview.webm'));
  check('recording download has bytes',fs.statSync(path.join(out,'actual-merged-manual-preview.webm')).size>1000);
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'live-mobile.png'),fullPage:true});
  check('responsive live no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  if(process.env.LIVE_COSMOS==='1'){
   assert(config.cosmos_enabled&&config.cosmos_configured,'Explicit live Cosmos server must be configured');
   await page.setViewportSize({width:1440,height:1000});
   const calls=[];
   for(const scenario of ['center','none']){
    // Same real robot-camera capture path used by operators. No annotation enters the model.
    await page.locator(`#scenarios [data-scenario="${scenario}"]`).click();
    await page.waitForTimeout(700);
    await page.locator('#analyse-button').click();
    let latest;
    for(let n=0;n<240;n++){
     await page.waitForTimeout(1000);latest=await (await context.request.get(base+'/api/live/'+sid)).json();
     if(latest.decision.status!=='pending')break;
    }
    calls.push({scenario,state:latest,provenance:'live_cosmos_robot_camera_on_synthetic_scene'});
    await page.screenshot({path:path.join(out,`live-cosmos-${scenario}.png`),fullPage:true});
    if(scenario==='none')check('actual no-fire inference never authorizes spray',latest.decision.status==='no_fire'&&!latest.spray.on,{status:latest.decision.status});
    else {
     check('actual visible-fire inference produces ready decision',latest.decision.status==='ready',{status:latest.decision.status});
     if(latest.decision.status==='ready'){
      await page.locator('#record-button').click();
      await page.waitForTimeout(11000);
      const outcome=await (await context.request.get(base+'/api/live/'+sid)).json();
      calls[calls.length-1].measured_after_response=outcome;
      check('live camera authorization produces actual ray suppression',outcome.metrics.hit_s>0&&outcome.fire.intensity<1,{hit_s:outcome.metrics.hit_s,intensity:outcome.fire.intensity});
      await page.screenshot({path:path.join(out,'live-cosmos-measured-suppression.png'),fullPage:true});
      await page.locator('#record-button').click();
      await page.waitForTimeout(500);
      const [authorizedDownload]=await Promise.all([page.waitForEvent('download'),page.locator('#video-download').click()]);
      await authorizedDownload.saveAs(path.join(out,'actual-live-authorized-suppression.webm'));
     }
    }
   }
   fs.writeFileSync(path.join(out,'live-cosmos-results.json'),JSON.stringify(calls,null,2));
   const liveEvidence=await (await context.request.get(base+'/api/live/'+sid+'/evidence')).json();
   fs.writeFileSync(path.join(out,'live-session-evidence.json'),JSON.stringify(liveEvidence,null,2));
  }
  await page.locator('#stop-button').click();
 }catch(e){checks.push({name:'browser journey completed',passed:false,error:e.message});console.error(e.stack);}
 finally{
  check('no browser JavaScript errors',errors.length===0,{errors});
  check('no broken app assets',failedAssets.length===0,{failedAssets});
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({base,provenance:process.env.FIXTURE_WORKFLOW==='1'?'MOCKED model service boundaries; actual ingest/confirmation/physics/export; not live inference':'actual_merged_app; manual preview unless live_cosmos explicitly recorded',checks,errors,failedAssets,unverified:['Operator-reviewed perception to confirmation flow needs authorized human reviewed video annotations; fixture workflow is mechanical QA only.']},null,2));
  await context.close();await browser.close();
 }
 process.exitCode=checks.some(c=>!c.passed)?1:0;
})().catch(e=>{console.error(e);process.exitCode=1;});
