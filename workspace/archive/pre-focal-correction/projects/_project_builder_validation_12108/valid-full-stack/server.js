const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
function createApp() { return http.createServer((request, response) => {
  if (request.url === '/health') { response.writeHead(200); return response.end('ok'); }
  if (request.url === '/api/notes') {
    const notes = fs.readFileSync(path.join(__dirname, 'data/notes.json'), 'utf8');
    response.writeHead(200, {'content-type': 'application/json'}); return response.end(notes);
  }
  response.writeHead(404); response.end('not found');
}); }
if (require.main === module) createApp().listen(Number(process.env.PORT) || 3000, '127.0.0.1');
module.exports = {createApp};
