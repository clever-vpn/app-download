import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const required = [
  "CF_WORKER_NAME",
  "CF_WORKER_KV_NAMESPACE_ID",
  "R2_BUCKET",
  "VERSION_KEY",
];

const missing = required.filter((key) => !process.env[key]);
if (missing.length > 0) {
  console.error(`Missing required environment variables: ${missing.join(", ")}`);
  process.exit(1);
}

const projectDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const contents = [
  `name = "${process.env.CF_WORKER_NAME}"`,
  'main = "src/index.js"',
  'compatibility_date = "2026-05-28"',
  'workers_dev = true',
  "",
  "[[kv_namespaces]]",
  'binding = "CLEVER_VPN_WWW_VERSION"',
  `id = "${process.env.CF_WORKER_KV_NAMESPACE_ID}"`,
  "",
  "[[r2_buckets]]",
  'binding = "WWW_DOWNLOAD"',
  `bucket_name = "${process.env.R2_BUCKET}"`,
  "",
  "[vars]",
  `VERSION_KEY = "${process.env.VERSION_KEY}"`,
  "",
].join("\n");

writeFileSync(resolve(projectDir, "wrangler.toml"), contents, "utf8");