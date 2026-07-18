import fs from 'fs';
import http from 'http';

const PORT = process.env.PORT || 3001;
let dbPath = './backend/persistence/data.json';

// Load persistence data safely with error handling for missing files
function loadDB() {
    try {
        const rawData = fs.readFileSync(dbPath, 'utf8');
        return JSON.parse(rawData);
    } catch (err) {
        console.warn(`Persistence file not found or unreadable: ${dbPath}. Using empty state.`);
        return { users: [] };
    }
}

// Save persistence data safely with error handling for write failures
function saveDB(data) {
    try {
        fs.writeFileSync(dbPath, JSON.stringify(data, null, 2), 'utf8');
        console.log('Data persisted successfully.');
    } catch (err) {
        console.error(`Failed to persist data: ${err.message}`);
    }
}

let db = loadDB();
const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    const response = JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() });
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(response);
  } else if (req.method === 'GET' && req.url.startsWith('/api/users')) {
    const response = JSON.stringify(db.users);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(response);
  } else {
    res.writeHead(404); 
    res.end('Not Found');
  }
});

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
