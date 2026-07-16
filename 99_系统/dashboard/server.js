// 指挥中心 · 零依赖本地服务器（Node 内置模块）
// 用法：node server.js  然后浏览器打开 http://localhost:4321
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 4321;
const DIR = __dirname;
const DATA_FILE = path.join(DIR, 'data.json');

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

function readData() {
  return JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
}

const server = http.createServer((req, res) => {
  // 读数据
  if (req.method === 'GET' && req.url === '/api/data') {
    try {
      return sendJson(res, 200, readData());
    } catch (e) {
      return sendJson(res, 500, { error: String(e) });
    }
  }

  // 写数据（整份覆盖）
  if (req.method === 'POST' && req.url === '/api/data') {
    let raw = '';
    req.on('data', (c) => (raw += c));
    req.on('end', () => {
      try {
        const obj = JSON.parse(raw);
        obj.meta = obj.meta || {};
        obj.meta.updated = new Date().toISOString();
        fs.writeFileSync(DATA_FILE, JSON.stringify(obj, null, 2), 'utf-8');
        return sendJson(res, 200, { ok: true, updated: obj.meta.updated });
      } catch (e) {
        return sendJson(res, 400, { error: String(e) });
      }
    });
    return;
  }

  // 首页
  if (req.method === 'GET' && (req.url === '/' || req.url === '/index.html')) {
    try {
      const html = fs.readFileSync(path.join(DIR, 'index.html'), 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      return res.end(html);
    } catch (e) {
      res.writeHead(500);
      return res.end('index.html 未找到');
    }
  }

  res.writeHead(404);
  res.end('Not Found');
});

server.listen(PORT, () => {
  console.log(`指挥中心已启动 → http://localhost:${PORT}`);
  console.log(`数据文件：${DATA_FILE}`);
});
