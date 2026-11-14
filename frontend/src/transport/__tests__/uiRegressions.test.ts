import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  deriveVideoStreamUiState,
  handleTreeRowDeleteKeyDown,
  resolvePreviewIframeSandbox,
  shouldTriggerTreeRowKeyboardSelect,
} from '../../features/uiGuards.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC_ROOT = path.resolve(__dirname, '../..');

describe('Pre-Merge UI & Security Regression Guards', () => {
  it('WorkspaceViewer preview iframes preserve browser storage on isolated preview origins while blocking same-origin escape', () => {
    // 1. Ephemeral preview origin distinct from Tauri host origin -> includes allow-same-origin
    const tauriPreviewPolicy = resolvePreviewIframeSandbox(
      'http://127.0.0.1:54322/index.html',
      'http://tauri.localhost'
    );
    assert.equal(
      tauriPreviewPolicy,
      'allow-scripts allow-forms allow-same-origin allow-modals'
    );
    assert.ok(!tauriPreviewPolicy.includes('allow-top-navigation'));
    assert.ok(!tauriPreviewPolicy.includes('allow-popups'));

    // 2. Ephemeral preview port distinct from Vite dev server port -> includes allow-same-origin
    const vitePreviewPolicy = resolvePreviewIframeSandbox(
      'http://127.0.0.1:59123/',
      'http://127.0.0.1:5173'
    );
    assert.equal(
      vitePreviewPolicy,
      'allow-scripts allow-forms allow-same-origin allow-modals'
    );

    // 3. Same-origin or about:blank or non-http URL -> omits allow-same-origin to prevent sandbox escape
    assert.equal(
      resolvePreviewIframeSandbox('http://tauri.localhost/malicious', 'http://tauri.localhost'),
      'allow-scripts allow-forms allow-modals'
    );
    assert.equal(
      resolvePreviewIframeSandbox('about:blank', 'http://tauri.localhost'),
      'allow-scripts allow-forms allow-modals'
    );
    assert.equal(
      resolvePreviewIframeSandbox('javascript:alert(1)', 'http://tauri.localhost'),
      'allow-scripts allow-forms allow-modals'
    );

    // 4. Verify WorkspaceViewer.tsx wires resolvePreviewIframeSandbox into both preview iframes
    const viewerSrc = fs.readFileSync(
      path.join(SRC_ROOT, 'features/workspace/WorkspaceViewer.tsx'),
      'utf8'
    );
    assert.ok(
      viewerSrc.includes('sandbox={resolvePreviewIframeSandbox(previewUrl)}'),
      'WorkspaceViewer.tsx must use resolvePreviewIframeSandbox(previewUrl)'
    );
    assert.ok(
      !viewerSrc.includes('sandbox="allow-scripts allow-forms"'),
      'WorkspaceViewer.tsx must not hardcode sandbox without allow-same-origin'
    );
  });

  it('CodeEditor TreeRow Delete button handles Enter and Space without triggering parent row selection', () => {
    const rowElement = { tag: 'div' };
    const deleteButtonElement = { tag: 'button' };

    let deletedPath: string | null = null;
    let selectedPath: string | null = null;

    for (const key of ['Enter', ' ']) {
      deletedPath = null;
      selectedPath = null;
      let defaultPrevented = false;
      let propagationStopped = false;

      // Child delete button receives keydown first
      const handledByDelete = handleTreeRowDeleteKeyDown(
        {
          key,
          preventDefault: () => {
            defaultPrevented = true;
          },
          stopPropagation: () => {
            propagationStopped = true;
          },
        },
        'src/App.tsx',
        (p) => {
          deletedPath = p;
        }
      );

      assert.equal(handledByDelete, true);
      assert.equal(deletedPath, 'src/App.tsx');
      assert.equal(defaultPrevented, true);
      assert.equal(propagationStopped, true);

      // Even if a synthetic event bubbled to parent row, target !== currentTarget blocks selection
      const shouldSelect = shouldTriggerTreeRowKeyboardSelect({
        key,
        target: deleteButtonElement,
        currentTarget: rowElement,
        defaultPrevented,
      });
      if (shouldSelect) {
        selectedPath = 'src/App.tsx';
      }
      assert.equal(shouldSelect, false);
      assert.equal(selectedPath, null);
    }

    // Pressing Enter/Space directly on the row itself still triggers selection
    assert.equal(
      shouldTriggerTreeRowKeyboardSelect({
        key: 'Enter',
        target: rowElement,
        currentTarget: rowElement,
        defaultPrevented: false,
      }),
      true
    );
    assert.equal(
      shouldTriggerTreeRowKeyboardSelect({
        key: ' ',
        target: rowElement,
        currentTarget: rowElement,
        defaultPrevented: false,
      }),
      true
    );

    const editorSrc = fs.readFileSync(
      path.join(SRC_ROOT, 'features/workspace/CodeEditor.tsx'),
      'utf8'
    );
    assert.ok(editorSrc.includes('shouldTriggerTreeRowKeyboardSelect(event)'));
    assert.ok(editorSrc.includes('handleTreeRowDeleteKeyDown(event, node.path, onDelete)'));
  });

  it('StudyVideoReaderView derives explicit loading, ready, error, and missing_media states', () => {
    // 1. Native desktop while mediaTicket is being fetched -> loading
    const loadingState = deriveVideoStreamUiState({
      isNativeDesktop: true,
      isTicketLoading: true,
      mediaTicket: null,
      mediaTicketError: false,
      videoStreamError: false,
      videoStreamUrl: undefined,
    });
    assert.equal(loadingState.status, 'loading');
    assert.equal(loadingState.showErrorBanner, false);
    assert.ok(loadingState.message?.includes('stream de vídeo'));

    // 2. Native desktop when getMediaTicket fails or returns null -> error
    const ticketErrorState = deriveVideoStreamUiState({
      isNativeDesktop: true,
      isTicketLoading: false,
      mediaTicket: null,
      mediaTicketError: true,
      videoStreamError: false,
      videoStreamUrl: undefined,
    });
    assert.equal(ticketErrorState.status, 'error');
    assert.equal(ticketErrorState.showErrorBanner, true);

    // 3. Missing media URL when not loading and no ticket error -> missing_media
    const missingMediaState = deriveVideoStreamUiState({
      isNativeDesktop: false,
      isTicketLoading: false,
      mediaTicket: null,
      mediaTicketError: false,
      videoStreamError: false,
      videoStreamUrl: undefined,
    });
    assert.equal(missingMediaState.status, 'missing_media');
    assert.equal(missingMediaState.showErrorBanner, true);

    // 4. Valid ticket and URL -> ready
    const readyState = deriveVideoStreamUiState({
      isNativeDesktop: true,
      isTicketLoading: false,
      mediaTicket: 'ticket_ok_123',
      mediaTicketError: false,
      videoStreamError: false,
      videoStreamUrl: 'http://127.0.0.1:54321/api/study/document/doc1/video?ticket=ticket_ok_123',
    });
    assert.equal(readyState.status, 'ready');
    assert.equal(readyState.showErrorBanner, false);
    assert.equal(readyState.message, null);

    // 5. Verify StudyVideoReaderView.tsx renders loading, error, missing_media, and retry testids
    const videoViewSrc = fs.readFileSync(
      path.join(SRC_ROOT, 'features/study/StudyVideoReaderView.tsx'),
      'utf8'
    );
    assert.ok(videoViewSrc.includes('deriveVideoStreamUiState('));
    assert.ok(videoViewSrc.includes('data-testid="study-video-loading-state"'));
    assert.ok(videoViewSrc.includes('data-testid="study-video-retry-button"'));
  });
});
