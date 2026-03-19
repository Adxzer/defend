# defendts

TypeScript SDK for Defend guardrails.

- Install: `npm i defendts`
- Runtime: Node.js `>=18`

## Quick start

```ts
import { DefendClient, isBlocked } from "defendts";

const client = new DefendClient({ apiKey: "dev", baseUrl: "http://localhost:8000" });
const result = await client.input("Hello");

if (isBlocked(result)) {
  throw new Error("Blocked by guardrails");
}
```

## Repository and docs

Source, API docs, and full setup guide:

https://github.com/Adxzer/defend
