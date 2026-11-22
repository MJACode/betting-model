// The reference side of tests/test_pc_monitor_phone.py: build each QR code
// with qrcode-terminal (an independent implementation Expo installs under
// mobile/node_modules) and print every mask's module matrix as JSON.
//   node tests/qr_reference.js <path to qrcode-terminal> '<[["text","L"], ...]>'
const pkg = process.argv[2];
const QRCode = require(pkg + '/vendor/QRCode');
const LEVEL = require(pkg + '/vendor/QRCode/QRErrorCorrectLevel');
const cases = JSON.parse(process.argv[3]);
const out = cases.map(([text, level]) => {
  const qr = new QRCode(-1, LEVEL[level]);
  qr.addData(text);
  qr.make();
  const masks = [];
  for (let m = 0; m < 8; m++) {
    qr.makeImpl(false, m);
    const n = qr.getModuleCount();
    const rows = [];
    for (let r = 0; r < n; r++) {
      let s = '';
      for (let c = 0; c < n; c++) s += qr.isDark(r, c) ? '1' : '0';
      rows.push(s);
    }
    masks.push(rows);
  }
  return { version: qr.typeNumber, masks };
});
process.stdout.write(JSON.stringify(out));
