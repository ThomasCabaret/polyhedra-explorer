import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const host = "127.0.0.1";
const portArgument = process.argv.find((argument) => argument.startsWith("--port="));
const port = Number(portArgument?.slice("--port=".length) ?? process.env.PORT ?? 8000);

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  console.error("Port invalide. Utilisez par exemple --port=8080.");
  process.exit(1);
}

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".mjs", "text/javascript; charset=utf-8"],
  [".svg", "image/svg+xml; charset=utf-8"]
]);

function send(response, status, message) {
  response.writeHead(status, { "Content-Type": "text/plain; charset=utf-8" });
  response.end(message);
}

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? host}`);
    const pathname = decodeURIComponent(url.pathname);
    let requestedPath = pathname.endsWith("/") ? `${pathname}index.html` : pathname;
    requestedPath = requestedPath.replace(/^\/+/, "");

    const filePath = resolve(join(root, requestedPath));
    if (filePath !== root && !filePath.startsWith(`${root}${sep}`)) {
      send(response, 403, "Forbidden\n");
      return;
    }

    const file = await stat(filePath);
    if (!file.isFile()) {
      send(response, 404, "Not found\n");
      return;
    }

    response.writeHead(200, {
      "Cache-Control": "no-store",
      "Content-Type": contentTypes.get(extname(filePath).toLowerCase()) ?? "application/octet-stream"
    });
    createReadStream(filePath).pipe(response);
  } catch (error) {
    if (error?.code === "ENOENT") {
      send(response, 404, "Not found\n");
      return;
    }
    send(response, 400, "Bad request\n");
  }
});

server.listen(port, host, () => {
  console.log(`Polyhedra Explorer: http://${host}:${port}/`);
  console.log("Appuyez sur Ctrl+C pour arreter le serveur.");
});
