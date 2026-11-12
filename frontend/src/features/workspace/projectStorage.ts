export const STORAGE_FAV_KEY = 'jarvis.project.favorites';
export const STORAGE_RECENT_KEY = 'jarvis.project.recent';
export const STORAGE_VIEW_KEY = 'jarvis.project.view_mode';

export function readStringList(key: string): string[] {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

export function recordRecentProject(projectId: string) {
  if (!projectId) return;
  try {
    const next = [projectId, ...readStringList(STORAGE_RECENT_KEY).filter((id) => id !== projectId)].slice(0, 12);
    localStorage.setItem(STORAGE_RECENT_KEY, JSON.stringify(next));
  } catch {
    // Ignore storage write errors
  }
}

