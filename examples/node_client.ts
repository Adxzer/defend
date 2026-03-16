import axios from "axios";

const DEFEND_API_URL = process.env.DEFEND_API_URL || "http://localhost:8000";

async function guardInput(text: string, metadata?: any) {
  const payload: any = { text, metadata };
  const response = await axios.post(`${DEFEND_API_URL}/guard/input`, payload, {
    timeout: 10000,
  });
  return response.data;
}

async function guardOutput(text: string, sessionId?: string, metadata?: any) {
  const payload: any = { text, session_id: sessionId, metadata };
  const response = await axios.post(`${DEFEND_API_URL}/guard/output`, payload, {
    timeout: 10000,
  });
  return response.data;
}

async function main() {
  const inputResult = await guardInput("Hello from Node");
  console.log("input", inputResult);

  // In a real app you would call your own LLM here using inputResult.session_id as needed.
  const outputResult = await guardOutput("LLM response goes here", inputResult.session_id);
  console.log("output", outputResult);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

