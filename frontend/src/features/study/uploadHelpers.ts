import type { TauriSelectFileFilter } from '../../transport';
import type { SourceType } from './types';

export function basenameFromPath(filePath: string): string {
  const normalized = filePath.replace(/\\/g, '/');
  const idx = normalized.lastIndexOf('/');
  return idx >= 0 ? normalized.slice(idx + 1) : normalized;
}

export function titleFromFilename(filename: string): string {
  return filename.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ').trim();
}

export function inferContainerSourceType(filename: string): 'VIDEO' | 'PDF' | 'SLIDES' | 'TEXT' {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (['mp4', 'mkv', 'mov', 'webm', 'avi', 'wmv', 'm4v'].includes(ext)) {
    return 'VIDEO';
  }
  if (ext === 'pdf') {
    return 'PDF';
  }
  if (ext === 'pptx' || ext === 'ppt') {
    return 'SLIDES';
  }
  return 'TEXT';
}

export function inferLibrarySourceType(
  filename: string,
  options?: { undefinedForCommonDocs?: boolean }
): SourceType | undefined {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (['mp4', 'webm', 'mkv', 'mov', 'avi', 'wmv', 'm4v'].includes(ext)) {
    return 'VIDEO';
  }
  if (['mp3', 'wav', 'm4a', 'ogg', 'flac', 'aac', 'wma'].includes(ext)) {
    return 'AUDIO';
  }
  if (options?.undefinedForCommonDocs) {
    return undefined;
  }
  if (ext === 'pdf') {
    return 'PDF';
  }
  if (ext === 'pptx' || ext === 'ppt') {
    return 'PPTX';
  }
  return 'TXT';
}

export function readBrowserFileAsBase64(file: File): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const raw = String(reader.result || '');
      const idx = raw.indexOf(',');
      resolve(idx >= 0 ? raw.slice(idx + 1).trim() : raw.trim());
    };
    reader.onerror = () => reject(new Error(`Falha ao ler ${file.name}`));
    reader.readAsDataURL(file);
  });
}

export function getStudyDialogFilters(mode: 'file' | 'video'): TauriSelectFileFilter[] {
  if (mode === 'video') {
    return [
      {
        name: 'Vídeo & Áudio',
        extensions: ['mp4', 'webm', 'mkv', 'mov', 'avi', 'wmv', 'm4v', 'mp3', 'wav', 'm4a', 'ogg', 'flac', 'aac', 'wma'],
      },
    ];
  }
  return [
    {
      name: 'Materiais de Estudo',
      extensions: [
        'pdf', 'docx', 'pptx', 'txt', 'md', 'markdown',
        'png', 'jpg', 'jpeg', 'webp',
        'mp4', 'webm', 'mkv', 'mov', 'avi', 'wmv', 'm4v',
        'mp3', 'wav', 'm4a', 'ogg', 'flac', 'aac', 'wma',
      ],
    },
  ];
}
