import type { ChatMessage } from '../../protocol/websocket';

export interface ChatAttachment {
  id: string;
  name: string;
  type: 'image' | 'document' | 'code';
  size: number;
  mimeType: string;
  dataUrl?: string; // base64 / data URL for preview and transport
  textContent?: string; // extracted text content for context injection
  tokenEstimate?: number;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
  promptHistory: string[];
}

export type LogCategory = 'ALL' | 'SENTINEL' | 'WEBSOCKET' | 'PROJECT' | 'SECURITY' | 'SYSTEM' | 'ORCHESTRATOR';
export type LogLevel = 'info' | 'warning' | 'error' | 'benign' | 'success';

export interface SystemLogEntry {
  id: string;
  timestamp: string;
  category: LogCategory;
  level: LogLevel;
  message: string;
  source?: string;
  details?: Record<string, unknown>;
}
