import fs from 'fs';
import path from 'path';

const base = 'http://134.122.74.217:3001';

async function setPro(userId) {
  await fetch(`${base}/api/subscription/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId },
    body: JSON.stringify({ plan: 'pro' }),
  });
}

async function runVitd() {
  const userId = 'debug-vitd-case';
  await setPro(userId);
  const pdfPath = path.join('d:/23AIBox-DFinder', 'blood tests', 'blood test pdf vitamin d.pdf');
  const pdf = fs.readFileSync(pdfPath);
  const analyzeRes = await fetch(`${base}/api/analyze-pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId },
    body: JSON.stringify({ pdfBase64: pdf.toString('base64') }),
  });
  const analyzeJson = await analyzeRes.json().catch(() => ({}));
  console.log('vitd analyze', analyzeRes.status, analyzeJson);

  await fetch(`${base}/api/blood-tests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId },
    body: JSON.stringify(analyzeJson),
  });

  const latest = await (await fetch(`${base}/api/blood-tests/latest`, { headers: { 'x-user-id': userId } })).json();
  const active = await (await fetch(`${base}/api/virtual-medications/active`, { headers: { 'x-user-id': userId } })).json();
  console.log('vitd latest', latest);
  console.log('vitd active', active);
}

async function runQr() {
  const userId = 'debug-qr-case';
  await setPro(userId);
  const qrUrl = 'https://tahlilatic.dz/cr/26040881N3897/E333842/95106/Axuhs1UToSevFvo7YUHvHCJ9AKI4wD0uXaq';
  const qrRes = await fetch(`${base}/api/analyze-blood-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId },
    body: JSON.stringify({ url: qrUrl }),
  });
  const qrJson = await qrRes.json().catch(() => ({}));
  console.log('qr analyze', qrRes.status, qrJson);

  await fetch(`${base}/api/blood-tests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': userId },
    body: JSON.stringify(qrJson),
  });

  const latest = await (await fetch(`${base}/api/blood-tests/latest`, { headers: { 'x-user-id': userId } })).json();
  const active = await (await fetch(`${base}/api/virtual-medications/active`, { headers: { 'x-user-id': userId } })).json();
  console.log('qr latest', latest);
  console.log('qr active', active);
}

await runVitd();
await runQr();
