import { addTask, taskCountLabel } from './tasks.js';

export function createTaskState(values) {
  const tasks = values.reduce(addTask, []);
  return { tasks, label: taskCountLabel(tasks) };
}
