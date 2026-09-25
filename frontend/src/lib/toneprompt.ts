export type Tone = "analytical" | "direct" | "patient";

export const TONE_OPTIONS: { value: Tone; label: string }[] = [
  { value: "analytical", label: "Analytical" },
  { value: "direct", label: "Direct" },
  { value: "patient", label: "Patient" },
];

const TONE_PREFIXES: Record<Tone, string> = {
  analytical:
    "[Respond in an analytical, detailed tone with specific reasoning.]",
  direct: "[Respond in a direct, concise tone. Get straight to the point.]",
  patient:
    "[Respond in a patient, encouraging, beginner-friendly tone.]",
};

// Backend has no tone/personality parameter (CoachChatRequest is just
// {game_id, message}) — see the "Optional future tone field" proposal in
// API_CONTRACT.md. Until that ships, the tone is encoded as a bracketed
// instruction line prepended to the outgoing message. The backend persists
// whatever string it receives verbatim, so this prefix ends up permanently
// stored in chat_history — stripTonePrefix() below undoes that specifically
// when hydrating history from the backend, never on freshly-typed messages.
export function applyTonePrefix(tone: Tone, message: string): string {
  return `${TONE_PREFIXES[tone]}\n\n${message}`;
}

const STRIP_PATTERN = /^\[Respond in an? [^\]]*\]\n\n/;

export function stripTonePrefix(content: string): string {
  return content.replace(STRIP_PATTERN, "");
}
