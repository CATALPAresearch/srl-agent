// ESLint flat config (ESLint >= 9). Same rules as the former .eslintrc.js.
const pluginVue = require("eslint-plugin-vue");
const globals = require("globals");

module.exports = [
  ...pluginVue.configs["flat/essential"],
  {
    files: ["**/*.js", "**/*.vue"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser, ...globals.node },
    },
    rules: {
      "no-console": "off",
      "no-debugger": "warn",
      "vue/no-unused-vars": "warn",
      "vue/require-v-for-key": "error",
      "vue/no-use-v-if-with-v-for": "error",
    },
  },
];
