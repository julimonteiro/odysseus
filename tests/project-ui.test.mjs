import test from 'node:test';
import assert from 'node:assert/strict';
import { terminalMode, fileReferences, alignDiff } from '../static/js/projectDiff.js';
test('terminal mode requires ! in the first position',()=>{
  assert.equal(terminalMode('!pwd'),true);assert.equal(terminalMode('!'),true);
  assert.equal(terminalMode(' !pwd'),false);assert.equal(terminalMode('hello !pwd'),false);
});
test('references support spaces and deduplication',()=>{
  assert.deepEqual(fileReferences('see @{src/my file.py} and @src/main.py @src/main.py'),['src/my file.py','src/main.py']);
});
test('side by side diff aligns insertions and deletions',()=>{
  const rows=alignDiff('a\nb\nc','a\nx\nb\nc').rows;
  assert.equal(rows[1].left,null);assert.equal(rows[1].right.text,'x');assert.equal(rows[2].left.text,'b');
  assert.equal(alignDiff('<script>','changed').rows[0].left.text,'<script>');
});
test('modifications pair original and changed text in the same row',()=>{
  const rows=alignDiff('original\n','changed\n').rows;
  assert.equal(rows[0].left.text,'original');assert.equal(rows[0].right.text,'changed');
});
