export function normalizeTask(value) {
  return String(value ?? '').trim();
}

export function addTask(tasks, value) {
  const normalized = normalizeTask(value);
  return [...tasks, normalized];
}

export function taskCountLabel(tasks) {
  const count = tasks.length;
  if (count === 1) {
    return '1 task';
  }
  return `${count} tasks`;
}
