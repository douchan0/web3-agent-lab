export const UNIT = 10n ** 18n;
const BPS = 10000n;
export function units(text) {
  if (!/^\d{1,13}(\.\d{1,18})?$/.test(text)) throw Error("请输入正数，最多 18 位小数。");
  const [whole, fraction = ''] = text.split('.');
  const raw = BigInt(whole) * UNIT + BigInt(fraction.padEnd(18, '0'));
  if (raw <= 0n || raw > 10n ** 30n) throw Error("输入量须大于 0，且不超过 1 万亿。");
  return raw;
}
export function format(raw, digits = 18) {
  const number = BigInt(raw);
  const decimals = (number % UNIT).toString().padStart(18, '0').slice(0, digits).replace(/0+$/, '');
  return (number / UNIT).toString() + (decimals ? '.' + decimals : '');
}
export function quote(x, y, input) {
  if (x <= 0n || y <= 0n || input <= 0n) throw Error("储备和输入量必须为正。");
  const weighted = input * 997n;
  const out = weighted * y / (1000n * x + weighted);
  const fair = input * y;
  const impact = ((fair - out * x) * BPS + fair - 1n) / fair;
  return {out, impact, fee: input * 30n / BPS, before: x * y, after: (x + input) * (y - out)};
}
export function risk(input, opening, current, wallet) {
  if (input <= 0n || input > opening * 60n / BPS) return 'trade_limit';
  if (input > wallet) return 'balance';
  const first = quote(opening, opening, input);
  const now = quote(current, opening, input);
  if (now.impact > 100n) return 'price_impact';
  const minOut = (first.out * 9970n + 9999n) / BPS;
  return now.out < (minOut > 0n ? minOut : 1n) ? 'execution_slippage' : 'accepted';
}
