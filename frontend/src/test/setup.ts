import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no layout: the pieces of it that Radix Select calls are stubbed
const proto = Element.prototype;
proto.hasPointerCapture ??= () => false;
proto.setPointerCapture ??= () => {};
proto.releasePointerCapture ??= () => {};
proto.scrollIntoView ??= () => {};
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

afterEach(() => {
  cleanup();
  window.localStorage.clear(); // language, theme and query history are remembered there
});
