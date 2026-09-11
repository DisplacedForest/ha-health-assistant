import http from "node:http";
import { readFile } from "node:fs/promises";
const routes = new Map([
  ["/", ["frontend-src/test/fixtures/panel.html", "text/html"]],
  ["/fixture.js", ["frontend-src/test/fixtures/fixture.js", "text/javascript"]],
  ["/sparse.json", ["frontend-src/test/fixtures/sparse.json", "application/json"]],
  ["/panel.js", ["custom_components/health_assistant/frontend/dist/panel.js", "text/javascript"]],
]);
const server = http.createServer(async (request, response) => {
  const route = routes.get(request.url);
  if (!route) { response.writeHead(404); response.end(); return; }
  response.writeHead(200, { "Content-Type": route[1], "Cache-Control": "no-store" });
  response.end(await readFile(route[0]));
});
server.listen(0, "127.0.0.1", () => process.stdout.write(`http://127.0.0.1:${server.address().port}/\n`));
