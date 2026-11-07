const fs = require('node:fs');
const solc = require('solc');

const source = fs.readFileSync('contracts/Market.sol', 'utf8');
const input = {
  language: 'Solidity',
  sources: {'Market.sol': {content: source}},
  settings: {
    evmVersion: 'cancun',
    optimizer: {enabled: true, runs: 200},
    outputSelection: {'*': {'*': ['evm.bytecode.object', 'evm.methodIdentifiers']}},
  },
};
const output = JSON.parse(solc.compile(JSON.stringify(input)));
for (const error of output.errors ?? []) console.error(error.formattedMessage);
if (output.errors?.some(error => error.severity === 'error')) process.exit(1);
fs.mkdirSync('build', {recursive: true});
fs.writeFileSync('build/contracts.json', JSON.stringify({
  compiler: solc.version(),
  contracts: output.contracts['Market.sol'],
}, null, 2));
