// A new project's founder input (docs/plan/11-project-mode.md section 5.1): Adam's own words when
// he proposed it, and his answers to Jorah's onboarding questions, verbatim. The runner's setup run
// drafts the charter, questions, backlog and Adam's tasks from this file, so nothing in it is
// Jorah's: no summary, no filled-in intent.

export const MAX_WORDS = 8000;
export const MAX_ANSWERS = 5;
export const MAX_QUESTION = 300;
export const MAX_ANSWER = 2000;

export class IntakeError extends Error {}

// Control characters other than tab and newline are dropped; line ends become \n. Nothing else changes.
const verbatim = (s) => String(s).replace(/\r\n?/g, "\n").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, "");

/** Check Adam's words and answers. Returns { words, answers } or throws with what is wrong. */
export function checkIntake(words, answers) {
  const w = typeof words === "string" ? verbatim(words).trim() : "";
  if (!w) throw new IntakeError("give Adam's own words about the project");
  if (w.length > MAX_WORDS) throw new IntakeError(`Adam's words are longer than ${MAX_WORDS} characters`);
  if (answers !== undefined && answers !== null && !Array.isArray(answers)) throw new IntakeError("answers must be a list of { question, answer }");
  const list = answers ?? [];
  if (list.length > MAX_ANSWERS) throw new IntakeError(`at most ${MAX_ANSWERS} answers`);
  const out = list.map((a, i) => {
    const q = typeof a?.question === "string" ? verbatim(a.question).replace(/\s+/g, " ").trim() : "";
    const ans = typeof a?.answer === "string" ? verbatim(a.answer).trim() : "";
    if (!q || !ans) throw new IntakeError(`answer ${i + 1} needs both the question and Adam's answer`);
    if (q.length > MAX_QUESTION) throw new IntakeError(`question ${i + 1} is longer than ${MAX_QUESTION} characters`);
    if (ans.length > MAX_ANSWER) throw new IntakeError(`answer ${i + 1} is longer than ${MAX_ANSWER} characters`);
    return { question: q, answer: ans };
  });
  return { words: w, answers: out };
}

/** inbox/intake.md: "# Founder input", when and how, the words, then the answers. */
export function intakeText({ words, answers, at, via }) {
  const lines = ["# Founder input", "", `Given: ${at}`, `Via: ${via}`, "", words, ""];
  if (answers.length) {
    lines.push("## Answers", "");
    for (const a of answers) lines.push(`### ${a.question}`, "", a.answer, "");
  }
  return lines.join("\n");
}

// A note from Adam to a project that is already running (project_note): his words, verbatim,
// appended to the same inbox/intake.md under their own heading. The runner copies the file into
// the project when it changes and tells the next run that intake.md has new words, so a note needs
// no new protocol: it is founder input like the first message, and only the runner writes it.
export const MAX_NOTE = 4000;
export const MAX_INTAKE_BYTES = 200 * 1024; // the runner refuses an intake.md over 256 KB

/** Check one note's words. Returns them, verbatim but trimmed, or throws with what is wrong. */
export function checkNote(words) {
  const w = typeof words === "string" ? verbatim(words).trim() : "";
  if (!w) throw new IntakeError("give Adam's own words for the project");
  if (w.length > MAX_NOTE) throw new IntakeError(`Adam's words are longer than ${MAX_NOTE} characters`);
  return w;
}

/**
 * inbox/intake.md with one more note: the existing text, then "## Note from Adam, <at>, via <via>"
 * and his words. A project with no intake yet (imported from a repo) gets the header first, so the
 * file still follows the contract (check_intake_text).
 */
export function withNote(existing, { words, at, via }) {
  const head = typeof existing === "string" && existing.trim()
    ? existing.replace(/\s*$/, "\n")
    : ["# Founder input", "", `Given: ${at}`, `Via: ${via}`, ""].join("\n");
  return `${head}\n## Note from Adam, ${at}, via ${via}\n\n${words}\n`;
}
