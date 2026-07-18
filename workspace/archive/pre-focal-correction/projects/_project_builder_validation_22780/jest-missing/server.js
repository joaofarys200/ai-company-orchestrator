const http = require('node:http');

function createApp() {
  return http.createServer((request, response) => {
    if (request.url === '/health') {
      response.writeHead(200, {'content-type': 'application/json'});
      return response.end(JSON.stringify({status: 'ok'}));
    }
    response.writeHead(404); response.end('not found');
  });
}
if (require.main === module) {
  createApp().listen(Number(process.env.PORT) || 3000, '127.0.0.1');
}
module.exports = {createApp};
