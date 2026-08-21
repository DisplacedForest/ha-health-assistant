export default [
  {
    files: ["src/**/*.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        customElements: "readonly",
        window: "readonly",
        document: "readonly",
        Date: "readonly",
        Math: "readonly",
        Number: "readonly",
        Intl: "readonly",
        console: "readonly",
      },
    },
    rules: {
      "no-unused-vars": "error",
      "no-var": "error",
      "prefer-const": "error",
      eqeqeq: "error",
    },
  },
];
