const {chromium: browserType}=require('playwright-core');
const {readFileSync}=require('node:fs'); const assert=require('node:assert/strict');
// This test mutates an application, HR notes and AI config. It is strictly for
// an explicitly confirmed, disposable local synthetic environment.
const base=process.env.HRA_E2E_BASE_URL;
const fixturePath=process.env.HRA_E2E_FIXTURE;
const healthUrl=process.env.HRA_E2E_HEALTH_URL;
if (process.env.HRA_E2E_SYNTHETIC !== '1' || !base || !fixturePath || !healthUrl) {
 throw new Error('Set HRA_E2E_SYNTHETIC=1, HRA_E2E_BASE_URL, HRA_E2E_HEALTH_URL and HRA_E2E_FIXTURE for a disposable synthetic preview only.');
}
for (const url of [base, healthUrl]) {
 if (!['localhost','127.0.0.1','[::1]'].includes(new URL(url).hostname)) throw new Error('Test URLs must use a local loopback host.');
}
const f=JSON.parse(readFileSync(fixturePath,'utf8'));
const executablePath=process.env.HRA_E2E_CHROMIUM_EXECUTABLE;
const launchArgs=process.env.HRA_E2E_CHROMIUM_ARGS ? JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS) : [];
const waitText=async (page,text)=>page.getByText(text,{exact:false}).filter({visible:true}).first().waitFor({timeout:15000});
(async()=>{
 const health=await fetch(healthUrl);
 assert.equal(health.ok,true,'The local testing backend health endpoint must be reachable');
 assert.equal((await health.json()).environment,'testing','The backend must be in testing mode');
 // The operator must still verify that this backend uses the disposable DB;
 // a loopback URL or testing mode alone cannot prove that.
 const browser=await browserType.launch({args:launchArgs,executablePath,headless:true}); const errors=[]; let step='initial';
 function watch(p,who){p.on('pageerror',e=>errors.push(`${who} ${p.url()} (${step}): ${e.stack || e.message}`));p.on('response',r=>{if(r.status()>=500)errors.push(`${who}: HTTP ${r.status()} ${r.url()}`)});}
 const ctx=await browser.newContext({viewport:{width:1440,height:900}}); const page=await ctx.newPage();watch(page,'desktop');
 step='login initial';
 await page.goto(base+'/',{waitUntil:'domcontentloaded'});await waitText(page,'Sàng lọc CV với AI');
 assert.equal(await page.locator('html').getAttribute('lang'),'vi');
 await page.getByRole('button',{name:'English',exact:true}).click();await waitText(page,'AI CV screening');
 step='login reload';
 await page.reload({waitUntil:'domcontentloaded'});await waitText(page,'AI CV screening');assert.equal(await page.locator('html').getAttribute('lang'),'en');
 console.log('Login language switch and persistence: OK');
 // Simulated bad credentials: the login endpoint must use the same safe,
 // reactive server-message localization as the rest of the API client.
 step='login error';
 const loginRoute=/\/v1\/auth\/login$/;
 await page.route(loginRoute,route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({detail:'Invalid user credentials'})}));
 await page.locator('input[type="email"]').fill('synthetic@example.test');
 await page.locator('input[type="password"]').fill('synthetic-password');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await waitText(page,'Invalid user credentials');
 await page.getByRole('button',{name:'Tiếng Việt',exact:true}).click();await waitText(page,'Thông tin đăng nhập không hợp lệ.');
 await page.getByRole('button',{name:'English',exact:true}).click();await waitText(page,'Invalid user credentials');
 await page.unroute(loginRoute);
 console.log('Login error switches languages safely: OK');
 await page.evaluate(token=>localStorage.setItem('hra_access_token',token),f.hr_token);
 step='positions initial';
 await page.goto(base+'/positions',{waitUntil:'domcontentloaded'});await waitText(page,'Recruitment positions');await waitText(page,'Software Engineer (dữ liệu giả)');
 assert.equal((await page.locator('body').innerText()).includes('Đơn vị minh họa'),true);
 await page.getByRole('button',{name:'Tiếng Việt',exact:true}).click();await waitText(page,'Vị trí tuyển dụng');
 await page.getByRole('button',{name:'English',exact:true}).click();await waitText(page,'Recruitment positions');
 console.log('Positions and user-authored data across language changes: OK');
 // A server error already on screen must follow subsequent language switches.
 const positionsRoute=/\/v1\/positions\?.*$/;
 await page.route(positionsRoute, route=>route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({detail:'You do not have permission to access this position'})}));
 step='positions error reload';
 await page.reload({waitUntil:'domcontentloaded'});await waitText(page,'You do not have permission to access this position');
 await page.getByRole('button',{name:'Tiếng Việt',exact:true}).click();await waitText(page,'Bạn không có quyền truy cập vị trí này.');
 await page.getByRole('button',{name:'English',exact:true}).click();await waitText(page,'You do not have permission to access this position');
 // Repeated fast reloads exercise the SSR Emotion cache/hydration boundary.
 for (let i=0;i<5;i++) {
  step=`positions hydration reload ${i+1}`;
  await page.reload({waitUntil:'domcontentloaded'});
  await waitText(page,'You do not have permission to access this position');
 }
 await page.unroute(positionsRoute);
 console.log('Displayed backend error follows the selected language; repeated hydration: OK');
 step='position detail';
 await page.goto(`${base}/positions/${f.position}`,{waitUntil:'domcontentloaded'});await waitText(page,'Software Engineer (dữ liệu giả)');
 await page.getByRole('tab',{name:'Job description (JD)'}).click();await waitText(page,'Synthetic JD: Python engineering');
 await page.getByRole('button',{name:'Create a new JD version'}).click();
 let dialog=page.getByRole('dialog');await dialog.getByLabel('JD content').fill('Synthetic browser-only JD draft');
 assert.equal(await dialog.getByLabel('JD content').inputValue(),'Synthetic browser-only JD draft');
 await dialog.getByRole('button',{name:'Cancel'}).click();
 console.log('JD history and editable version dialog: OK');
 step='candidate detail';
 await page.goto(`${base}/positions/${f.position}/applicants/${f.app_c}`,{waitUntil:'domcontentloaded'});
 await waitText(page,'Ứng viên giả Chi');
 await page.getByRole('button',{name:/Candidate profile/}).click();
 await page.getByRole('button',{name:'Edit profile',exact:true}).click();
 dialog=page.getByRole('dialog');await dialog.getByLabel('Candidate name').fill('Ứng viên giả Chi');
 if (await dialog.getByLabel('Name',{exact:true}).count() === 0) await dialog.getByRole('button',{name:'Add item',exact:true}).click();
 await dialog.getByLabel('Name',{exact:true}).last().fill('Synthetic Python skill');
 await dialog.getByRole('button',{name:'Save new version'}).click();
 await waitText(page,'Profile version saved.');await waitText(page,'Synthetic Python skill');
 assert.equal((await page.locator('body').innerText()).includes('Ứng viên giả Chi'),true);
 await page.getByRole('button',{name:/HR-only internal notes/}).click();
 await page.getByLabel('Add an internal note').fill('Synthetic HR-only test note');
 await page.getByRole('button',{name:'Add note',exact:true}).click();await waitText(page,'Synthetic HR-only test note');
 console.log('HR profile version and internal note saved via UI: OK');
 step='admin';
 await page.goto(base+'/admin',{waitUntil:'domcontentloaded'});await waitText(page,'AI administration');
 await page.getByLabel('Temperature',{exact:true}).fill('1.5');await page.getByRole('button',{name:'Create and activate'}).click();
 await waitText(page,'Choose an approved model and endpoint, and a temperature between 0 and 1.');
 await page.getByRole('button',{name:'Tiếng Việt',exact:true}).click();await waitText(page,'Vui lòng chọn model, endpoint và temperature trong khoảng 0–1.');
 await page.getByRole('button',{name:'English',exact:true}).click();await waitText(page,'Choose an approved model and endpoint, and a temperature between 0 and 1.');
 await page.getByLabel('Temperature',{exact:true}).fill('0.2');
 await page.getByRole('combobox',{name:'Approved model'}).click();
 await page.getByRole('option',{name:'synthetic-alternative-model'}).click();
 await page.getByRole('button',{name:'Create and activate'}).click();await waitText(page,'Configuration activated. Running jobs continue using their pinned configuration.');
 const active=await page.request.get(base+'/v1/admin/ai/active-config',{headers:{Authorization:`Bearer ${f.hr_token}`}});assert.equal(active.status(),200);assert.equal((await active.json()).config.model_name,'synthetic-alternative-model');
 console.log('Admin validation, live locale change and AI config activation: OK');
 const hm=await browser.newContext({viewport:{width:1440,height:900}});await hm.addInitScript(([token])=>{localStorage.setItem('hra_access_token',token);localStorage.setItem('hra_locale','en')},[f.hm_token]);
 const hp=await hm.newPage();watch(hp,'HM');await hp.goto(`${base}/positions/${f.position}/applicants/${f.app_b}`,{waitUntil:'domcontentloaded'});
 await waitText(hp,'Ứng viên giả Bình');assert.equal(await hp.getByText('HR-only internal notes').count(),0);assert.equal(await hp.getByText('Candidate profile').count(),0);
 await waitText(hp,'This assessment was shared in summary-only mode.');
 const hmDetail=await hp.request.get(`${base}/v1/applications/${f.app_b}`,{headers:{Authorization:`Bearer ${f.hm_token}`}});
 assert.equal(hmDetail.status(),200); const summary=await hmDetail.json();
 assert.equal(summary.identity.email,null); assert.equal(summary.identity.phone,null);
 assert.deepEqual(summary.documents,[]); assert.equal(summary.file_processing_status,'UNKNOWN');
 assert.equal(summary.can_view_assessment_evidence,false);
 const forbidden=await hp.request.get(`${base}/v1/applications/${f.app_b}/private-notes`,{headers:{Authorization:`Bearer ${f.hm_token}`}});assert.equal(forbidden.status(),403);
 console.log('HM summary-only access excludes contact details, profile, CV and internal notes: OK');
 const mobile=await browser.newContext({viewport:{width:390,height:844}});await mobile.addInitScript(([token])=>{localStorage.setItem('hra_access_token',token);localStorage.setItem('hra_locale','en')},[f.hr_token]);
 const mp=await mobile.newPage();watch(mp,'mobile');await mp.goto(base+'/positions',{waitUntil:'domcontentloaded'});await waitText(mp,'Software Engineer (dữ liệu giả)');
 const width=await mp.evaluate(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));assert.ok(width.scroll<=width.client+1,JSON.stringify(width));
 await mp.getByRole('button',{name:'Open navigation menu'}).click();await mp.getByRole('link',{name:'Work overview'}).click();await waitText(mp,'Total applications');
 await mp.getByRole('button',{name:'Tiếng Việt',exact:true}).click();await waitText(mp,'Tổng hồ sơ');
 console.log(`Mobile navigation, bilingual toggle, width ${width.scroll}/${width.client}: OK`);
 await browser.close();if(errors.length)throw Error(errors.join('\n'));console.log('No browser page errors or HTTP 5xx responses');
})().catch(e=>{console.error(e);process.exit(1)});
