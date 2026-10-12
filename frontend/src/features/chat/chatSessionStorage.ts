import type { ChatSession } from './types';
import type { ChatMessage } from '../../protocol/websocket';

const STORAGE_KEY_SESSIONS = 'jarvis_chat_sessions_v2';
const STORAGE_KEY_PROMPTS = 'jarvis_chat_prompt_history_v1';
const MAX_SESSIONS = 50;
const MAX_MESSAGES_PER_SESSION = 150;
const MAX_PROMPTS_HISTORY = 60;

function safeLocalStorageGet(key: string): string | null {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      return window.localStorage.getItem(key);
    }
  } catch (err) {
    console.warn(`[ChatStorage] Error reading ${key} from localStorage:`, err);
  }
  return null;
}

function safeLocalStorageSet(key: string, value: string): void {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(key, value);
    }
  } catch (err) {
    console.warn(`[ChatStorage] Error writing ${key} to localStorage:`, err);
  }
}

export function generateSessionId(): string {
  return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

export function generateSmartSessionTitle(firstPrompt: string): string {
  const clean = firstPrompt.trim().replace(/^[/@][\w-]+\s*/, '');
  if (!clean) return 'Nova conversa';
  const firstLine = clean.split('\n')[0].trim();
  if (firstLine.length <= 40) return firstLine;
  return `${firstLine.slice(0, 37)}...`;
}

export function createDefaultSession(): ChatSession {
  return {
    id: generateSessionId(),
    title: 'Nova conversa',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
    promptHistory: [],
  };
}

export function loadStoredChatSessions(): ChatSession[] {
  const raw = safeLocalStorageGet(STORAGE_KEY_SESSIONS);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed.map((item) => ({
        id: String(item.id || generateSessionId()),
        title: String(item.title || 'Conversa'),
        createdAt: Number(item.createdAt) || Date.now(),
        updatedAt: Number(item.updatedAt) || Date.now(),
        messages: Array.isArray(item.messages) ? item.messages : [],
        promptHistory: Array.isArray(item.promptHistory) ? item.promptHistory : [],
      }));
    }
  } catch (err) {
    console.warn('[ChatStorage] Failed to parse stored sessions:', err);
  }
  return [];
}

export function persistChatSessions(sessions: ChatSession[]): void {
  try {
    // Sanitize sessions before storing to stay well under local storage quota (5MB)
    // Strip large image dataUrls if session has more than 10 messages
    const sanitized = sessions.slice(0, MAX_SESSIONS).map((s) => ({
      ...s,
      messages: s.messages.slice(-MAX_MESSAGES_PER_SESSION).map((m: ChatMessage) => {
        if (!m.attachments || m.attachments.length === 0) return m;
        return {
          ...m,
          attachments: m.attachments.map((att) => ({
            id: att.id,
            name: att.name,
            type: att.type,
            size: att.size,
            mimeType: att.mimeType,
            // Keep textContent or short previews, strip massive raw dataUrls if older
            textContent: att.textContent ? att.textContent.slice(0, 4000) : undefined,
            dataUrl: att.type === 'image' && att.dataUrl && att.dataUrl.length < 150000 ? att.dataUrl : undefined,
          })),
        };
      }),
    }));
    safeLocalStorageSet(STORAGE_KEY_SESSIONS, JSON.stringify(sanitized));
  } catch (err) {
    console.warn('[ChatStorage] Failed to persist chat sessions:', err);
  }
}

export function loadStoredPromptHistory(): string[] {
  const raw = safeLocalStorageGet(STORAGE_KEY_PROMPTS);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.filter((p) => typeof p === 'string' && p.trim().length > 0).slice(0, MAX_PROMPTS_HISTORY);
    }
  } catch (err) {
    console.warn('[ChatStorage] Failed to load prompt history:', err);
  }
  return [];
}

export function persistPromptHistory(prompts: string[]): void {
  try {
    const unique = Array.from(new Set(prompts.filter(Boolean))).slice(-MAX_PROMPTS_HISTORY);
    safeLocalStorageSet(STORAGE_KEY_PROMPTS, JSON.stringify(unique));
  } catch (err) {
    console.warn('[ChatStorage] Failed to persist prompt history:', err);
  }
}

export function formatSessionGroupDate(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Hoje';
  if (diffDays === 1) return 'Ontem';
  if (diffDays < 7) return 'Últimos 7 dias';
  if (diffDays < 30) return 'Últimos 30 dias';
  return 'Anteriores';
}
