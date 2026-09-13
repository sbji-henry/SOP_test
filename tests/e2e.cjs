const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.BASE_URL || 'http://127.0.0.1:8080';
const data = require('../data/workflows.json');

(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH}:{}), args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100}});
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
    await page.goto(base);
    await page.locator('#selected-workflow').waitFor({state:'visible'});
    assert.equal(await page.locator('.workflow-card').count(),12);
    for(const w of data.workflows) {
      await page.locator(`[data-wf="${w.id}"]`).click();
      await page.waitForFunction(id=>document.querySelector('#selected-id').textContent===id&&!document.querySelector('#selected-workflow').hidden,w.id);
      assert.equal(await page.locator('#graph .graph-node').count(),w.nodes.length+1);
      for(const n of w.nodes) {
        await page.locator(`#graph [data-node="${n.id}"]`).click();
        assert.equal(await page.locator('#evidence-content blockquote').textContent(),n.text);
      }
    }
    console.log('PASS: 12 workflows, 51 graph nodes and exact evidence quotations');
    await page.locator('#search').fill('CBS');
    await page.waitForFunction(()=>document.querySelector('#result-count').textContent==='1');
    assert.equal(await page.locator('#selected-id').textContent(),'WF-007');
    await page.locator('#phase').selectOption('수습·복구');
    await page.locator('#selection-empty').waitFor({state:'visible'});
    assert.equal(await page.locator('#selected-workflow').isVisible(),false);
    await page.locator('#reset').click();
    await page.waitForFunction(()=>document.querySelector('#result-count').textContent==='12');
    await page.locator('#agency').selectOption('대변인');
    await page.waitForFunction(()=>document.querySelector('#selected-id').textContent==='WF-010'&&!document.querySelector('#selected-workflow').hidden);
    assert.equal(await page.locator('.workflow-card').count(),1);
    await page.locator('#actions-tab').click();
    await page.locator('#actions-panel').waitFor({state:'visible'});
    await page.locator('.action-item').last().click();
    assert.match(await page.locator('#evidence-content').textContent(),/수습상황/);
    await page.locator('#graph-tab').click();
    const originalView=await page.locator('#graph').getAttribute('viewBox');
    await page.locator('#zoom-in').click();
    assert.notEqual(await page.locator('#graph').getAttribute('viewBox'),originalView);
    await page.locator('#zoom-reset').click();
    assert.equal(await page.locator('#graph').getAttribute('viewBox'),originalView);
    await page.locator('#source-info').click();
    assert.equal(await page.locator('#source-dialog').isVisible(),true);
    assert.match(await page.locator('#source-content').textContent(),new RegExp(data.source.sha256));
    await page.keyboard.press('Escape');
    console.log('PASS: search, phase/agency intersection, empty state, reset, tabs, zoom, source dialog');
    await page.goto(base+'/#wf=WF-011&node=WF-011-N02');
    await page.locator('#selected-workflow').waitFor({state:'visible'});
    assert.equal(await page.locator('#evidence-content h4').textContent(),'뒷불감시 인력 배치');
    assert.equal(await page.locator('.graph-arrow').count(),1);
    await page.locator('#graph [data-node="WF-011-N01"]').focus();
    await page.keyboard.press('Enter');
    assert.match(page.url(),/node=WF-011-N01/);
    console.log('PASS: deep link, explicit sequence edge, keyboard graph selection');
    await page.goto(base+'/#wf=WF-007');
    await page.locator('#selected-workflow').waitFor({state:'visible'});
    fs.mkdirSync('test-results',{recursive:true});
    await page.screenshot({path:'test-results/desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.locator('#actions-tab').click();
    await page.locator('.action-item').last().click();
    await page.screenshot({path:'test-results/mobile.png',fullPage:true});
    console.log('PASS: mobile layout, no horizontal page overflow, node selection');
    assert.deepEqual(errors,[]);
    // Failure must clear stale content and recover on the next successful search.
    await page.route('**/api/workflows?**',route=>route.abort('failed'));
    await page.locator('#search').fill('test error');
    await page.waitForFunction(()=>document.querySelector('#status').classList.contains('error'));
    assert.equal(await page.locator('#selected-workflow').isVisible(),false);
    await page.unroute('**/api/workflows?**');
    await page.locator('#reset').click();
    await page.locator('#selected-workflow').waitFor({state:'visible'});
    console.log('PASS: network error clears stale results and recovers');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
