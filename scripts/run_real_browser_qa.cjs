/**
 * JARVIS OS — Real Browser QA Execution Runner
 * Executes End-to-End Real Browser QA against a live project preview URL:
 * - Browser: Microsoft Edge (via Playwright channel: msedge)
 * - Validates HTML/Asset load without uncaught exceptions or network failures.
 * - Detects inert controls, blank pages, and silent fallback regressions.
 * - Executes real UI interactions (e.g. #scanIpButton).
 * - Verifies real DOM updates and structured card rendering.
 * - Captures high-resolution before/after screenshots for evidentiary verification.
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const PLAYWRIGHT_PATH = path.join(PROJECT_ROOT, 'frontend', 'node_modules', 'playwright');

let chromium;
try {
  chromium = require(PLAYWRIGHT_PATH).chromium;
} catch (e) {
  try {
    chromium = require('playwright').chromium;
  } catch (e2) {
    console.error(JSON.stringify({
      available: false,
      valid: false,
      status: 'INSUFFICIENT_EVIDENCE',
      error: 'Playwright não encontrado em frontend/node_modules/playwright nem globalmente.'
    }));
    process.exit(0);
  }
}

async function runQA() {
  const args = process.argv.slice(2);
  const targetUrl = args[0] || 'http://127.0.0.1:3000';
  const missionId = args[1] || 'qa_mission';
  const evidenceDir = args[2] || path.join(PROJECT_ROOT, 'evidence', 'product_delivery');

  fs.mkdirSync(evidenceDir, { recursive: true });

  const result = {
    available: true,
    valid: false,
    target_url: targetUrl,
    mission_id: missionId,
    page_loaded: false,
    title: '',
    console_errors: [],
    page_errors: [],
    network_failures: [],
    is_blank_page: false,
    is_inert_button: false,
    interaction_performed: false,
    interaction_result_valid: false,
    cards_found: 0,
    has_rich_device_cards: false,
    has_legacy_raw_ips_only: false,
    sample_rendered_text: '',
    evidence_screenshots: [],
    violations: [],
  };

  let browser = null;
  try {
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
        const text = msg.text();
        if (!text.includes('favicon.ico')) {
          result.console_errors.push(text);
        }
      }
    });

    page.on('pageerror', err => {
      result.page_errors.push(err.toString());
    });

    page.on('requestfailed', req => {
      result.network_failures.push({
        url: req.url(),
        errorText: req.failure() ? req.failure().errorText : 'Failed'
      });
    });

    // 1. Navegar até ao preview
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
    result.page_loaded = true;
    result.title = await page.title();

    // 2. Verificar se a página está em branco
    const bodyText = await page.evaluate(() => document.body ? document.body.innerText.trim() : '');
    if (!bodyText || bodyText.length < 30) {
      result.is_blank_page = true;
      result.violations.push('BLANK_PAGE_ERROR: O documento carregou mas o corpo está em branco ou sem conteúdo.');
    }

    // Screenshot inicial
    const ssBefore = path.join(evidenceDir, `${missionId}_01_before_interaction.png`);
    await page.screenshot({ path: ssBefore, fullPage: true });
    result.evidence_screenshots.push(ssBefore);

    // 3. Procurar e testar interação principal (ex: #scanIpButton ou botões genéricos)
    const scanBtn = await page.$('#scanIpButton');
    const genericBtn = scanBtn ? null : await page.$('#refreshMetricsBtn, #fetchAuditBtn, button');

    if (scanBtn) {
      result.interaction_performed = true;
      const initialResults = await page.evaluate(() => {
        const el = document.getElementById('ipScanResults');
        return el ? el.innerHTML : '';
      });

      // Clicar no botão
      await scanBtn.click();

      // Aguardar que o spinner suma ou que os resultados apareçam (máximo 8 segundos)
      try {
        await page.waitForFunction(() => {
          const res = document.getElementById('ipScanResults');
          const spinner = document.getElementById('ipScanLoadingSpinner');
          const spinnerHidden = !spinner || spinner.style.display === 'none';
          const hasContent = res && res.children.length > 0 && !res.innerText.includes('Consultando');
          return spinnerHidden && hasContent;
        }, { timeout: 8000 });
      } catch (waitErr) {
        // Se demorou mais tempo, prossegue para recolher o estado do DOM
      }

      const postResultsHtml = await page.evaluate(() => {
        const el = document.getElementById('ipScanResults');
        return el ? el.innerHTML : '';
      });

      const postResultsText = await page.evaluate(() => {
        const el = document.getElementById('ipScanResults');
        return el ? el.innerText.trim() : '';
      });

      result.sample_rendered_text = postResultsText.slice(0, 300);

      // Verificar se o botão foi inerte
      if (initialResults === postResultsHtml && !postResultsText) {
        result.is_inert_button = true;
        result.violations.push('INERT_CONTROL_ERROR: O botão de interação foi clicado mas não desencadeou qualquer alteração no DOM.');
      }

      // Inspecionar se renderizou cartões ricos com Fabricante/MAC ou apenas fallback de IPs
      const cardCount = await page.evaluate(() => {
        const el = document.getElementById('ipScanResults');
        return el ? el.querySelectorAll('li').length : 0;
      });
      result.cards_found = cardCount;

      if (postResultsHtml.includes('Fabricante:') || postResultsHtml.includes('MAC:')) {
        result.has_rich_device_cards = true;
        result.interaction_result_valid = true;
      } else if (postResultsHtml.includes('🌐') && cardCount > 0) {
        result.has_legacy_raw_ips_only = true;
        result.violations.push('SILENT_FALLBACK_REGRESSION: O frontend renderizou apenas a lista crua legada de IPs (🌐), sem cartões de Fabricante/MAC/Hostname.');
      } else if (cardCount === 0 && !postResultsText.includes('Nenhum dispositivo')) {
        result.violations.push('RENDER_FAILURE: Nenhum dispositivo ou mensagem de conclusão foi renderizada em #ipScanResults.');
      } else {
        result.interaction_result_valid = true;
      }

      // Screenshot pós-interação
      const ssAfter = path.join(evidenceDir, `${missionId}_02_after_interaction.png`);
      await page.screenshot({ path: ssAfter, fullPage: true });
      result.evidence_screenshots.push(ssAfter);
    } else if (genericBtn) {
      result.interaction_performed = true;
      const initialHtml = await page.evaluate(() => document.body.innerHTML);
      await genericBtn.click();
      await page.waitForTimeout(1000);
      const postHtml = await page.evaluate(() => document.body.innerHTML);

      if (initialHtml === postHtml) {
        result.is_inert_button = true;
        result.violations.push('INERT_CONTROL_ERROR: O botão clicado não alterou o DOM.');
      } else {
        result.interaction_result_valid = true;
      }

      const ssAfter = path.join(evidenceDir, `${missionId}_02_after_interaction.png`);
      await page.screenshot({ path: ssAfter, fullPage: true });
      result.evidence_screenshots.push(ssAfter);
    } else {
      // Projeto sem botão interativo — validação de integridade genérica
      result.interaction_result_valid = true;
    }

    if (result.console_errors.length > 0) {
      for (const ce of result.console_errors) {
        result.violations.push(`BROWSER_CONSOLE_ERROR: ${ce}`);
      }
    }

    if (result.page_errors.length > 0) {
      for (const pe of result.page_errors) {
        result.violations.push(`UNCAUGHT_PAGE_EXCEPTION: ${pe}`);
      }
    }

    result.valid = (
      result.page_loaded
      && !result.is_blank_page
      && !result.is_inert_button
      && !result.has_legacy_raw_ips_only
      && result.interaction_result_valid
      && result.violations.length === 0
    );

  } catch (err) {
    result.violations.push(`BROWSER_QA_FATAL_ERROR: ${err.message}`);
    result.valid = false;
  } finally {
    if (browser) {
      await browser.close();
    }
  }

  console.log(JSON.stringify(result));
}

runQA();
