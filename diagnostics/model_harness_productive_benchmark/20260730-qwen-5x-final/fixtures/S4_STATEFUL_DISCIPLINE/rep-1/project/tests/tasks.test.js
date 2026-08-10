import assert from 'node:assert/strict';
import { addTask, taskCountLabel } from '../src/tasks.js';

assert.deepEqual(addTask([], ' buy milk '), ['buy milk']);
assert.equal(taskCountLabel([]), '0 tasks');
assert.equal(taskCountLabel(['one']), '1 task');
assert.equal(taskCountLabel(['one', 'two']), '2 tasks');
console.log('fixture tests passed');
