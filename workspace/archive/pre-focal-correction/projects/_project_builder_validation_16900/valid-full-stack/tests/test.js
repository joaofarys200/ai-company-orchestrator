const http = require('node:http');
const {createApp} = require('../server.js');
const server = createApp().listen(0, '127.0.0.1', () => {
  const port = server.address().port;
  http.get(`http://127.0.0.1:${port}/health`, response => {
    if (response.statusCode !== 200) process.exitCode = 1;
    response.resume(); response.on('end', () => server.close());
  }).on('error', error => { console.error(error); process.exitCode = 1; server.close(); });
});
