const functions = require("firebase-functions");

const SMPL_API_BASE = "https://airavat-backend-u3hyo7liyq-uc.a.run.app";

async function doFetch(url, options) {
  const { default: fetch } = await import("node-fetch");
  return fetch(url, options);
}

exports.smpl = functions.https.onRequest(async (req, res) => {
  res.set("Access-Control-Allow-Origin", "*");
  res.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.set("Access-Control-Allow-Headers", "Content-Type, Authorization");
  if (req.method === "OPTIONS") {
    return res.status(204).send("");
  }

  try {
    const targetUrl = `${SMPL_API_BASE}${req.url}`;

    const upstream = await doFetch(targetUrl, {
      method: req.method,
      headers: { "Content-Type": req.get("Content-Type") || "application/json" },
      body: ["GET", "HEAD"].includes(req.method) ? undefined : JSON.stringify(req.body),
    });

    const contentType = upstream.headers.get("content-type") || "application/json";
    res.set("Content-Type", contentType);
    const buffer = await upstream.arrayBuffer();
    res.status(upstream.status).send(Buffer.from(buffer));
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Proxy error", details: String(err) });
  }
});

