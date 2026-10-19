import { boot, state, navigate } from "./core.js";

window.addEventListener("hashchange", () => {
  if (state.me) navigate(location.hash.slice(1));
});

boot();
