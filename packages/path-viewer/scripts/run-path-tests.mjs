import { Window } from "happy-dom";
import react from "@vitejs/plugin-react";
import { createServer } from "vite";

const root = new URL("..", import.meta.url).pathname;

const dom = new Window({ url: "http://127.0.0.1:8080/" });
function expose(name, value) {
  try {
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
  } catch {
    globalThis[name] = value;
  }
}

expose("window", dom);
expose("document", dom.document);
expose("HTMLElement", dom.HTMLElement);
expose("SVGElement", dom.SVGElement);
expose("Element", dom.Element);
expose("Node", dom.Node);
expose("navigator", dom.navigator);
expose("localStorage", dom.localStorage);
expose("sessionStorage", dom.sessionStorage);
expose("getComputedStyle", dom.getComputedStyle.bind(dom));
expose("requestAnimationFrame", (callback) => setTimeout(() => callback(Date.now()), 0));
expose("cancelAnimationFrame", clearTimeout);
expose("IS_REACT_ACT_ENVIRONMENT", true);
if (!dom.matchMedia) {
  dom.matchMedia = () => ({
    matches: true,
    media: "",
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent() {
      return false;
    },
  });
}
expose("matchMedia", dom.matchMedia.bind(dom));
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
expose("ResizeObserver", ResizeObserverStub);
if (!dom.HTMLElement.prototype.scrollIntoView) {
  dom.HTMLElement.prototype.scrollIntoView = function scrollIntoView() {};
}

const server = await createServer({
  configFile: false,
  root,
  plugins: [
    {
      name: "css-stub",
      enforce: "pre",
      resolveId(id) {
        if (id.endsWith(".css")) return `\0${id}`;
      },
      load(id) {
        if (id.startsWith("\0") && id.endsWith(".css")) return "export default {}";
      },
    },
    react(),
  ],
  resolve: { alias: { "@": `${root}/src` } },
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "error",
});

const files = [
  "/src/lib/path/i18n.test.ts",
  "/src/lib/path/store.test.ts",
  "/src/components/path/view.test.tsx",
];

let failed = 0;
let passed = 0;

for (const file of files) {
  const mod = await server.ssrLoadModule(file);
  for (const [name, fn] of Object.entries(mod)) {
    if (!name.startsWith("test") || typeof fn !== "function") continue;
    try {
      await fn();
      passed += 1;
      console.log(`ok ${file} ${name}`);
    } catch (error) {
      failed += 1;
      console.error(`fail ${file} ${name}`);
      console.error(error);
    }
  }
}

await server.close();
dom.close();
console.log(`# path tests ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
