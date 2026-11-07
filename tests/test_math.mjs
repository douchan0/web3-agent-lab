import test from 'node:test';
import assert from 'node:assert/strict';
import {UNIT, units, quote, risk} from '../app/lab/math.mjs';

test('AMM exact wei matches deep and shallow Anvil receipts', () => {
  const deep = quote(10000n*UNIT,10000n*UNIT,units('18'));
  const shallow = quote(3000n*UNIT,3000n*UNIT,units('18'));
  assert.equal(deep.out,17913851801556925940n);
  assert.equal(shallow.out,17839285394768494863n);
  assert.equal(deep.impact,48n);
  assert.equal(shallow.impact,90n);
  assert.ok(deep.after > deep.before);
});
test('dust, precision and risk cap match contract and strategy boundaries', () => {
  const reserve = units('10000');
  assert.equal(quote(reserve,reserve,1n).out,0n);
  assert.throws(() => units('0.0000000000000000001'));
  assert.equal(risk(units('60'),reserve,reserve,units('250')),'accepted');
  assert.equal(risk(units('60.000000000000000001'),reserve,reserve,units('250')),'trade_limit');
});
