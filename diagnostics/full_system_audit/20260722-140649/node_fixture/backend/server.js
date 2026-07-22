import http from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const port = Number(process.env.PORT || 0);
const dataPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "data.json");

async function readRecords() {
  try {
    return JSON.parse(await readFile(dataPath, "utf8"));
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    await writeFile(dataPath, "[]\n", "utf8");
    return [];
  }
}

async function writeRecords(records) {
  await writeFile(dataPath, `${JSON.stringify(records)}\n`, "utf8");
}

const server = http.createServer(async (request, response) => {
  try {
    if (request.url === "/health" && request.method === "GET") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ status: "ok" }));
      return;
    }

    if (request.url === "/records" && request.method === "GET") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify(await readRecords()));
      return;
    }

    if (request.url === "/records" && request.method === "POST") {
      let body = "";
      for await (const chunk of request) body += chunk;
      const records = await readRecords();
      records.push(JSON.parse(body));
      await writeRecords(records);
      response.writeHead(201, { "content-type": "application/json" });
      response.end(JSON.stringify(records.at(-1)));
      return;
    }

    response.writeHead(404);
    response.end("Not Found");
  } catch (error) {
    response.writeHead(500, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: error.message }));
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(JSON.stringify({ status: "listening", port: server.address().port }));
});

function shutdown() {
  server.close(() => process.exit(0));
}

process.once("SIGTERM", shutdown);
process.once("SIGINT", shutdown);
