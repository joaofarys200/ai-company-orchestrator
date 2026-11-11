import type { DailyQueueItem, DailyReviewQueue, StudySessionItemRef, StudySessionState } from './types';

export type DailySessionTargetTab = 'flashcards' | 'active_recall' | 'quiz';

/**
 * Normalizes an ordered list of mixed typed items from all 4 daily review categories
 * (`lapsed`, `due`, `low_confidence`, `new`), avoiding duplicates and preserving
 * configured daily limits and original queue ordering.
 */
export function buildDailySessionItems(queue: DailyReviewQueue): StudySessionItemRef[] {
  const maxReviews = Math.max(1, Number(queue.daily_review_limit || 30));
  const maxNew = Math.max(0, Number(queue.daily_new_limit ?? 10));

  const reviewBuckets: Array<{ cat: 'lapsed' | 'due' | 'low_confidence'; list: DailyQueueItem[] }> = [
    { cat: 'lapsed', list: queue.lapsed_items || [] },
    { cat: 'due', list: queue.due_items || [] },
    { cat: 'low_confidence', list: queue.low_confidence_items || [] },
  ];

  const out: StudySessionItemRef[] = [];
  const seen = new Set<string>();
  let reviewCount = 0;

  for (const { cat, list } of reviewBuckets) {
    for (const raw of list) {
      if (reviewCount >= maxReviews) break;
      const iid = String(raw?.item_id || '').trim();
      if (!iid || seen.has(iid)) continue;
      seen.add(iid);
      reviewCount += 1;
      const rawType = String(raw.item_type || '').trim().toLowerCase();
      out.push({
        item_id: iid,
        item_type: rawType === 'active_recall' ? 'active_recall' : 'flashcard',
        queue_category: (raw.queue_category as StudySessionItemRef['queue_category']) || cat,
        title: raw.title || '',
        topic: raw.topic || '',
        chapter_id: raw.chapter_id || '',
        section_id: raw.section_id || '',
      });
    }
  }

  let newCount = 0;
  for (const raw of queue.new_items || []) {
    if (newCount >= maxNew) break;
    const iid = String(raw?.item_id || '').trim();
    if (!iid || seen.has(iid)) continue;
    seen.add(iid);
    newCount += 1;
    const rawType = String(raw.item_type || '').trim().toLowerCase();
    out.push({
      item_id: iid,
      item_type: rawType === 'active_recall' ? 'active_recall' : 'flashcard',
      queue_category: (raw.queue_category as StudySessionItemRef['queue_category']) || 'new',
      title: raw.title || '',
      topic: raw.topic || '',
      chapter_id: raw.chapter_id || '',
      section_id: raw.section_id || '',
    });
  }

  return out;
}

/**
 * Resolves typed items for a StudySessionState, providing safe compatibility fallback
 * for legacy persisted sessions containing only `item_ids`. Never inspects ID prefixes.
 */
export function getSessionItems(session: StudySessionState | null | undefined): StudySessionItemRef[] {
  if (!session) return [];
  const seen = new Set<string>();

  if (Array.isArray(session.items) && session.items.length > 0) {
    const out: StudySessionItemRef[] = [];
    for (const raw of session.items) {
      const iid = String(raw?.item_id || '').trim();
      if (!iid || seen.has(iid)) continue;
      seen.add(iid);
      const rawType = String(raw?.item_type || '').trim().toLowerCase();
      out.push({
        ...raw,
        item_id: iid,
        item_type: rawType === 'active_recall' ? 'active_recall' : 'flashcard',
      });
    }
    return out;
  }

  const fallbackType: 'flashcard' | 'active_recall' =
    session.mode === 'ACTIVE_RECALL' ? 'active_recall' : 'flashcard';
  const legacy: StudySessionItemRef[] = [];
  for (const rawId of session.item_ids || []) {
    const iid = String(rawId || '').trim();
    if (!iid || seen.has(iid)) continue;
    seen.add(iid);
    legacy.push({ item_id: iid, item_type: fallbackType });
  }
  return legacy;
}

export function getCurrentSessionItem(
  session: StudySessionState | null | undefined
): StudySessionItemRef | null {
  if (!session || session.status === 'COMPLETED' || session.status === 'ABANDONED') {
    return null;
  }
  const items = getSessionItems(session);
  if (items.length === 0) return null;
  const idx = Math.max(0, Math.min(items.length - 1, Number(session.current_index || 0)));
  return items[idx] || null;
}

export function isSessionAllItemsCompleted(session: StudySessionState | null | undefined): boolean {
  if (!session) return false;
  const items = getSessionItems(session);
  if (items.length === 0) return false;
  const completedSet = new Set((session.completed_item_ids || []).map((x) => String(x).trim()));
  return items.every((it) => completedSet.has(it.item_id));
}

export function resolveTabForSessionItem(
  item: StudySessionItemRef | null,
  sessionMode?: string
): DailySessionTargetTab {
  if (item) {
    const t = String(item.item_type || '').toLowerCase();
    if (t === 'active_recall') return 'active_recall';
    return 'flashcards';
  }
  if (sessionMode === 'ACTIVE_RECALL') return 'active_recall';
  if (sessionMode === 'ASSESSMENT') return 'quiz';
  return 'flashcards';
}

