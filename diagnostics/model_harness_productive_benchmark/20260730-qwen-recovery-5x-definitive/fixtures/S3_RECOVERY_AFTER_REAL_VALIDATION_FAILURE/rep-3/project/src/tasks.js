export function normalizeTask(value {
  return String(value ?? '').trim();
}

export function addTask(tasks, value) {
  if (typeof value !== 'string' || !value.trim()) {
    return tasks;
  }
  const normalized = normalizeTask(value);
  return [...tasks, normalized];
}

export function taskCountLabel(tasks) {
  return `${tasks.length} tasks`;
}
