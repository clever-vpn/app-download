const SEMVER_FRAGMENT = "v\\d+\\.\\d+\\.\\d+";

export default {
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD" },
      });
    }

    let objectPath;
    try {
      objectPath = normalizeObjectPath(new URL(request.url).pathname);
    } catch {
      return new Response("Invalid path", { status: 400 });
    }

    if (!objectPath) {
      return new Response("Missing file path", { status: 400 });
    }

    const versionKey = env.VERSION_KEY || "download-version";
    const downloadVersion = await env.CLEVER_VPN_WWW_VERSION.get(versionKey);
    if (!downloadVersion) {
      return new Response(`KV key ${versionKey} is not set`, { status: 500 });
    }

    const exactKey = `${downloadVersion}/${objectPath}`;
    const exactObject = await env.WWW_DOWNLOAD.get(exactKey);
    if (exactObject) {
      return buildObjectResponse(exactObject, request.method);
    }

    const fallbackKey = await findFallbackKey(env.WWW_DOWNLOAD, downloadVersion, objectPath);
    if (!fallbackKey) {
      return new Response("Not Found", { status: 404 });
    }

    const fallbackObject = await env.WWW_DOWNLOAD.get(fallbackKey);
    if (!fallbackObject) {
      return new Response("Not Found", { status: 404 });
    }

    return buildObjectResponse(fallbackObject, request.method);
  },
};

function normalizeObjectPath(pathname) {
  const decoded = decodeURIComponent(pathname).replace(/^\/+/, "");
  if (!decoded) {
    return null;
  }

  const segments = decoded.split("/");
  if (segments.some((segment) => !segment || segment === "." || segment === "..")) {
    return null;
  }

  return segments.join("/");
}

function splitDirAndFile(objectPath) {
  const lastSlash = objectPath.lastIndexOf("/");
  if (lastSlash === -1) {
    return { dir: "", fileName: objectPath };
  }

  return {
    dir: objectPath.slice(0, lastSlash),
    fileName: objectPath.slice(lastSlash + 1),
  };
}

function buildFallbackPattern(fileName) {
  const firstDash = fileName.indexOf("-");
  if (firstDash !== -1) {
    const prefix = escapeRegex(fileName.slice(0, firstDash));
    const suffix = escapeRegex(fileName.slice(firstDash));
    return new RegExp(`^${prefix}-${SEMVER_FRAGMENT}${suffix}$`);
  }

  const lastDot = fileName.lastIndexOf(".");
  if (lastDot === -1) {
    return new RegExp(`^${escapeRegex(fileName)}-${SEMVER_FRAGMENT}$`);
  }

  const base = escapeRegex(fileName.slice(0, lastDot));
  const ext = escapeRegex(fileName.slice(lastDot));
  return new RegExp(`^${base}-${SEMVER_FRAGMENT}${ext}$`);
}

async function findFallbackKey(bucket, downloadVersion, objectPath) {
  const { dir, fileName } = splitDirAndFile(objectPath);
  const pattern = buildFallbackPattern(fileName);
  const listPrefix = dir ? `${downloadVersion}/${dir}/` : `${downloadVersion}/`;

  let cursor;

  do {
    const listed = await bucket.list({ prefix: listPrefix, cursor });

    for (const object of listed.objects) {
      const candidateName = object.key.slice(listPrefix.length);
      if (candidateName.includes("/")) {
        continue;
      }

      if (pattern.test(candidateName)) {
        return object.key;
      }
    }

    cursor = listed.truncated ? listed.cursor : undefined;
  } while (cursor);

  return null;
}

function buildObjectResponse(object, method) {
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("accept-ranges", "bytes");

  if (object.size !== undefined) {
    headers.set("content-length", String(object.size));
  }

  if (method === "HEAD") {
    return new Response(null, { headers });
  }

  return new Response(object.body, { headers });
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}