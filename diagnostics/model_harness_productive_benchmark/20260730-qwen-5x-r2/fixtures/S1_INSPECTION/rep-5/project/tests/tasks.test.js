import assert from 'node:assert/strict';
import { addTask, taskCountLabel } from '../src/tasks.js';

assert.deepEqual(addTask([], ' buy milk '), ['buy milk']);
assert.deepEqual(addTask(['existing'], '   '), ['existing']);
assert.equal(taskCountLabel([]), '0 tasks');
console.log('fixture tests passed');
