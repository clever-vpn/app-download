import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const required = [
  "CLOUDFLARE_ACCOUNT_ID",
  "CLOUDFLARE_WORKER_NAME",
  "CLOUDFLARE_WORKER_KV_NAMESPACE_ID",
  "CLOUDFLARE_WORKER_R2_BUCKET",
  "VERSION_KEY",
];

const missing = required.filter((key) => !process.env[key]);
if (missing.length > 0) {
  console.error(`Missing required environment variables: ${missing.join(", ")}`);
  process.exit(1);
}

const projectDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const contents = [
  `name = "${process.env.CLOUDFLARE_WORKER_NAME}"`,
  'main = "src/index.js"',
  'compatibility_date = "2026-05-28"',
  'workers_dev = true',
  `account_id = "${process.env.CLOUDFLARE_ACCOUNT_ID}"`,
  "",
  "[[kv_namespaces]]",
  'binding = "CLEVER_VPN_WWW_VERSION"',
  `id = "${process.env.CLOUDFLARE_WORKER_KV_NAMESPACE_ID}"`,
  "",
  "[[r2_buckets]]",
  'binding = "WWW_DOWNLOAD"',
  `bucket_name = "${process.env.CLOUDFLARE_WORKER_R2_BUCKET}"`,
  "",
  "[vars]",
  `VERSION_KEY = "${process.env.VERSION_KEY}"`,
  "",
].join("\n");

writeFileSync(resolve(projectDir, "wrangler.toml"), contents, "utf8");