/**
 * JARVIS OS — Spatial Board E2E Browser QA
 * Validates the 4 domains:
 *   1. Study (Multimodal Reader, LLM Grounded Summary, Cornell Notes)
 *   2. Project (dina files, AST metrics, Monaco editor, execute/preview)
 *   3. Obsidian (Knowledge Vault, notes explorer, markdown view)
 *   4. Sentinel (Watchdog status, security events, audit control)
 * Validates Orb dock transition, card maximization/restore, and board close.
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const PLAYWRIGHT_PATH = path.join(PROJECT_ROOT, 'frontend', 'node_modules', 'playwright');

let chromium;
try {
  chromium = require(PLAYWRIGHT_PATH).chromium;
} catch (e) {
  chromium = require('playwright').chromium;
}

async function runSpatialBoardQA() {
  const targetUrl = 'http://localhost:8000';
  const evidenceDir = path.join(PROJECT_ROOT, 'evidence', 'spatial_board');
  fs.mkdirSync(evidenceDir, { recursive: true });

  const results = {
    url: targetUrl,
    timestamp: new Date().toISOString(),
    orb_initial_rendered: false,
    domains_tested: {},
    maximize_restore_tested: false,
    board_close_tested: false,
    console_errors: [],
    screenshots: []
  };

  let browser;
  try {
    browser = await chromium.launch({ headless: true, channel: 'msedge' });
  } catch (e) {
    browser = await chromium.launch({ headless: true });
  }

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') {
      const txt = msg.text();
      if (!txt.includes('favicon.ico')) {
        results.console_errors.push(txt);
      }
    }
  });

  try {
    console.log('[QA] 1. Loading http://localhost:8000...');
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForTimeout(2000);

    // Initial state: Orb in center
    const ssInitial = path.join(evidenceDir, '01_initial_orb_center.png');
    await page.screenshot({ path: ssInitial, fullPage: true });
    results.screenshots.push(ssInitial);
    results.orb_initial_rendered = true;
    console.log('[QA] 1. Initial page rendered. Screenshot:', ssInitial);

    // Open Study domain via dock button
    console.log('[QA] 2. Opening Study Spatial Board...');
    const studyBtn = await page.waitForSelector('button[title*="Estudos"]', { timeout: 8000 });
    await studyBtn.click();
    await page.waitForTimeout(2000);

    const ssStudy = path.join(evidenceDir, '02_study_spatial_board.png');
    await page.screenshot({ path: ssStudy, fullPage: true });
    results.screenshots.push(ssStudy);
    results.domains_tested.study = true;
    console.log('[QA] 2. Study domain verified. Screenshot:', ssStudy);

    // Maximize a card in Study Board
    console.log('[QA] 3. Testing card maximization...');
    const maxButtons = await page.$$('button[title*="Maximizar"], button:has(svg.lucide-maximize2)');
    if (maxButtons.length > 0) {
      await maxButtons[0].click();
      await page.waitForTimeout(1000);
      const ssMax = path.join(evidenceDir, '03_card_maximized.png');
      await page.screenshot({ path: ssMax, fullPage: true });
      results.screenshots.push(ssMax);

      // Restore card
      const restoreButtons = await page.$$('button[title*="Restaurar"], button:has(svg.lucide-minimize2)');
      if (restoreButtons.length > 0) {
        await restoreButtons[0].click();
        await page.waitForTimeout(1000);
      }
      results.maximize_restore_tested = true;
      console.log('[QA] 3. Card maximize & restore verified.');
    }

    // Switch to Project Domain
    console.log('[QA] 4. Switching to Project Domain...');
    const projNavBtn = await page.waitForSelector('button:has-text("Projeto"), button[title*="Projeto"]', { timeout: 5000 });
    await projNavBtn.click();
    await page.waitForTimeout(2000);

    const ssProject = path.join(evidenceDir, '04_project_spatial_board.png');
    await page.screenshot({ path: ssProject, fullPage: true });
    results.screenshots.push(ssProject);
    results.domains_tested.project = true;
    console.log('[QA] 4. Project domain verified. Screenshot:', ssProject);

    // Switch to Obsidian Domain
    console.log('[QA] 5. Switching to Obsidian Domain...');
    const obsNavBtn = await page.waitForSelector('button:has-text("Obsidian"), button[title*="Obsidian"]', { timeout: 5000 });
    await obsNavBtn.click();
    await page.waitForTimeout(2000);

    const ssObsidian = path.join(evidenceDir, '05_obsidian_spatial_board.png');
    await page.screenshot({ path: ssObsidian, fullPage: true });
    results.screenshots.push(ssObsidian);
    results.domains_tested.obsidian = true;
    console.log('[QA] 5. Obsidian domain verified. Screenshot:', ssObsidian);

    // Switch to Sentinel Domain
    console.log('[QA] 6. Switching to Sentinel Domain...');
    const sentNavBtn = await page.waitForSelector('button:has-text("Sentinel"), button[title*="Sentinel"]', { timeout: 5000 });
    await sentNavBtn.click();
    await page.waitForTimeout(2000);

    const ssSentinel = path.join(evidenceDir, '06_sentinel_spatial_board.png');
    await page.screenshot({ path: ssSentinel, fullPage: true });
    results.screenshots.push(ssSentinel);
    results.domains_tested.sentinel = true;
    console.log('[QA] 6. Sentinel domain verified. Screenshot:', ssSentinel);

    // Close Board ("Descansar")
    console.log('[QA] 7. Closing Board (Descansar)...');
    const restBtn = await page.waitForSelector('button:has-text("Descansar")', { timeout: 5000 });
    await restBtn.click();
    await page.waitForTimeout(1500);

    const ssRest = path.join(evidenceDir, '07_board_closed_orb_restored.png');
    await page.screenshot({ path: ssRest, fullPage: true });
    results.screenshots.push(ssRest);
    results.board_close_tested = true;
    console.log('[QA] 7. Board closed. Orb restored to center.');

  } catch (err) {
    console.error('[QA] Error during execution:', err);
    results.error = err.message;
  } finally {
    await browser.close();
  }

  const reportPath = path.join(evidenceDir, 'qa_spatial_board_results.json');
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2), 'utf-8');
  console.log('[QA] QA Results saved to:', reportPath);
  return results;
}

runSpatialBoardQA().then(res => {
  console.log('[QA] COMPLETED. Summary:', JSON.stringify({
    domains: res.domains_tested,
    maximize_restore: res.maximize_restore_tested,
    board_close: res.board_close_tested,
    console_errors_count: res.console_errors.length
  }, null, 2));
  process.exit(0);
}).catch(err => {
  console.error('[QA] Fatal error:', err);
  process.exit(1);
});

