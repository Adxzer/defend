import axios from "axios";

const DEFEND_API_URL = process.env.DEFEND_API_URL || "http://localhost:8000";

async function classify(text: string, sessionId?: string) {
  const payload: any = { text };
  if (sessionId) {
    payload.session_id = sessionId;
  }

  const response = await axios.post(`${DEFEND_API_URL}/classify`, payload, {
    timeout: 10000,
  });

  return response.data;
}

async function main() {
  const result = await classify("Hello from Node", "demo-session");
  console.log(result);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

