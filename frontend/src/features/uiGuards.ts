/**
 * Pure UI security, accessibility, and media-state guards shared across
 * WorkspaceViewer, CodeEditor, and StudyVideoReaderView.
 */

export interface VideoStreamUiState {
  status: 'loading' | 'ready' | 'error' | 'missing_media';
  showErrorBanner: boolean;
  message: string | null;
}

/**
 * Computes the iframe sandbox policy for project previews.
 * Grants `allow-same-origin` only when the preview URL runs on an isolated origin
 * distinct from the host shell origin (e.g. `http://127.0.0.1:<ephemeral_port>` vs
 * `http://tauri.localhost`), preserving browser storage (`localStorage`, `sessionStorage`,
 * `indexedDB`) inside previewed apps while preventing same-origin sandbox escape.
 */
export function resolvePreviewIframeSandbox(previewUrl: string | undefined, hostOrigin?: string): string {
  const basePolicy = 'allow-scripts allow-forms allow-modals';
  if (!previewUrl || previewUrl === 'about:blank') {
    return basePolicy;
  }
  try {
    const parsed = new URL(previewUrl);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return basePolicy;
    }
    const activeHostOrigin =
      hostOrigin !== undefined
        ? hostOrigin
        : typeof window !== 'undefined' && window.location
          ? window.location.origin
          : '';
    if (activeHostOrigin && parsed.origin.toLowerCase() === activeHostOrigin.toLowerCase()) {
      return basePolicy;
    }
    return 'allow-scripts allow-forms allow-same-origin allow-modals';
  } catch {
    return basePolicy;
  }
}

/**
 * Prevents keyboard events (Enter / Space) originating from nested interactive
 * controls (e.g. the file delete button inside `TreeRow`) from triggering row selection.
 */
export function shouldTriggerTreeRowKeyboardSelect(event: {
  key: string;
  target: unknown;
  currentTarget: unknown;
  defaultPrevented?: boolean;
}): boolean {
  if (event.defaultPrevented) return false;
  if (event.target !== event.currentTarget) return false;
  return event.key === 'Enter' || event.key === ' ';
}

/**
 * Handles Enter / Space key activation on the `TreeRow` delete button, stopping
 * propagation to the parent row container and invoking `onDelete(path)`.
 */
export function handleTreeRowDeleteKeyDown(
  event: {
    key: string;
    preventDefault: () => void;
    stopPropagation: () => void;
  },
  path: string,
  onDelete?: (path: string) => void
): boolean {
  if ((event.key === 'Enter' || event.key === ' ') && onDelete) {
    event.preventDefault();
    event.stopPropagation();
    onDelete(path);
    return true;
  }
  return false;
}

/**
 * Derives deterministic loading, ready, error, and missing-media states for
 * `StudyVideoReaderView`.
 */
export function deriveVideoStreamUiState(params: {
  isNativeDesktop: boolean;
  isTicketLoading: boolean;
  mediaTicket: string | null;
  mediaTicketError: boolean;
  videoStreamError: boolean;
  videoStreamUrl: string | undefined;
}): VideoStreamUiState {
  if (params.isNativeDesktop && params.isTicketLoading) {
    return {
      status: 'loading',
      showErrorBanner: false,
      message: 'A autenticar e preparar stream de vídeo seguro...',
    };
  }
  if (params.videoStreamError || params.mediaTicketError) {
    return {
      status: 'error',
      showErrorBanner: true,
      message:
        'O fluxo de vídeo (.wmv/.mkv ou stream local) ainda está a ser convertido para MP4 ou encontra-se indisponível nesta sessão.',
    };
  }
  if (!params.videoStreamUrl || !String(params.videoStreamUrl).trim()) {
    return {
      status: 'missing_media',
      showErrorBanner: true,
      message: 'Nenhum recurso de media disponível para este documento.',
    };
  }
  return {
    status: 'ready',
    showErrorBanner: false,
    message: null,
  };
}
