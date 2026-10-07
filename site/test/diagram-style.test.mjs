import test from 'node:test';
import assert from 'node:assert/strict';
import { diagramTextColor, diagramWidth } from '../src/lib/diagram-style.mjs';

test('diagram text contrasts with both pale and dark node fills', () => {
  for (const fill of ['#e9f4ed', '#DBF1E5', '#FFF0D5', '#FBE1E1', 'rgb(241, 232, 223)']) {
    assert.equal(diagramTextColor(fill), '#1a1a1a');
  }
  for (const fill of ['#162b22', 'rgb(30, 45, 36)']) {
    assert.equal(diagramTextColor(fill), '#ffffff');
  }
});

test('diagram display is reduced while retaining a scrollable mobile minimum', () => {
  assert.equal(diagramWidth(2000), 1680);
  assert.equal(diagramWidth(500), 720);
});
