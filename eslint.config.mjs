// Lint do JS do tablet (web/) e da extensão (extension/). Regras novas entram como aviso
// enquanto o código antigo tiver casos; quando zerar, viram erro (ver docs/quality.md).
import js from "@eslint/js";
import globals from "globals";

// Chrome/Edge/Opera não têm o global `browser` (só o Firefox): a extensão usa esse nome pra outra coisa.
const { browser: _firefoxOnly, ...webext } = globals.webextensions;
const warnAll = Object.fromEntries(Object.keys(js.configs.recommended.rules).map((r) => [r, "warn"]));

export default [
  { ignores: ["web/fonts/**", "web/icons/**", "web/pad-presets/**"] },
  {
    files: ["web/**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "script", globals: { ...globals.browser, YT: "readonly" } }, // YT = API do player do YouTube
    rules: warnAll,
  },
  {
    files: ["web/sw.js"],
    languageOptions: { globals: { ...globals.serviceworker } },
  },
  {
    files: ["extension/**/*.js"],
    languageOptions: { ecmaVersion: "latest", sourceType: "script", globals: { ...globals.browser, ...webext } },
    rules: warnAll,
  },
];
