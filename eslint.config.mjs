import tsParser from "@typescript-eslint/parser";

const eslintConfig = [
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "dist/**",
      "build/**",
      "out/**",
      "coverage/**",
      "skills/**",
      "examples/**",
      "mini-services/**",
      "*.config.*",
      "postcss.config.mjs",
      "next-env.d.ts",
      "tool-results/**",
    ],
  },
  {
    files: ["**/*.{ts,tsx,js,jsx,mjs,cjs}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaFeatures: { modules: true, jsx: true },
        ecmaVersion: 2022,
        sourceType: "module",
      },
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        process: "readonly",
        fetch: "readonly",
        AbortController: "readonly",
        FileReader: "readonly",
        Blob: "readonly",
        navigator: "readonly",
        URL: "readonly",
        Response: "readonly",
        Request: "readonly",
        ReadableStream: "readonly",
        TextDecoder: "readonly",
        TextEncoder: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        JSX: "readonly",
      },
    },
    rules: {
      "no-unused-vars": "off",
      "no-empty": "off",
      "no-undef": "off",
      "prefer-const": "warn",
      "no-irregular-whitespace": "off",
    },
  },
];

export default eslintConfig;
