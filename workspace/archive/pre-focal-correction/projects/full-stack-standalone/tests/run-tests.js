import http from 'http';

const PORT = 3001;
let serverStarted = false;

async function startServer() {
  return new Promise((resolve, reject) => {
    const srv = http.createServer();
    // Minimal mock for testing without full backend dependency in test suite if needed,
    // but here we assume the real server logic is tested against a running instance.
    srv.listen(PORT);
    resolve(srv);
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runTests() {
  console.log('Starting test suite...');
  
  try {
    const server = await startServer();
    // Simulate a simple health check request to verify the backend is up
    return new Promise((resolve, reject) => {
      http.get(`http://localhost:${PORT}/health`, (res) => {
        if (res.statusCode === 200) {
          console.log('Test passed: Health endpoint responds correctly.');
          server.close();
          resolve(true);
        } else {
          reject(new Error('Health check failed'));
        }
      }).on('error', err => {
        reject(err);
      });
    });
  } catch (err) {
    console.error('Test suite failed:', err.message);
    throw err;
  }
}

runTests().catch(console.error);