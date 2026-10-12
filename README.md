# Recruiting Agent: Customer Support Specialist

A small Claude agent that screens job applications. It uses real tool calls to score each one and choose a next step. Every action goes through guardrails that run in code.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then put your ANTHROPIC_API_KEY in .env

pytest                          # offline guardrail tests, no API key needed
python agent.py                 # reviews the 3 samples in applications.json
```

Outputs:
- **Console**: score, reason, action, status and flags for each candidate.
- `output/decisions.json`: the final record for each candidate.
- `output/audit_log.jsonl`: every event. That covers each LLM request and response, each tool call and its input, each tool result, guardrail blocks, injection detections and decisions.

Options: `--file other_apps.json`, `--out dir`, `MODEL=... python agent.py` (default `claude-opus-5-5`).

## How it works

```
application ─► pre-scan (regex) ─► wrap in <application> envelope ─► Claude
                                                                       │ tool calls
                     audit_log.jsonl ◄── CandidateExecutor ◄───────────┘
                                         (policy gate in code)
```

Each candidate gets its own conversation with a manual tool-use loop (`agent.py`). The model has five tools (`tools.py`):

| Tool | Effect |
|---|---|
| `score_application` | Records the rubric breakdown (experience /40, tools & volume /20, communication /20, availability /20), the total and a reason. Must come first. |
| `flag_suspicious_content` | Reports text that tries to instruct the model. |
| `advance_to_interview` | Sets status `interview_invited`. |
| `reject` | Sets status **`waiting for human approval`**. Nothing the agent does can make a rejection final. |
| `request_more_info` | Records follow-up questions. Sets status `awaiting_candidate_reply`. |

## Handling prompt injection (sample C)

Application text is treated as **data, never instructions**. The model's own judgement is not the only protection, because a model that follows the injected text would also follow it while "checking" itself. So the defences are layered, and the important ones run in code:

1. **Data envelope.** The text goes inside `<application>` tags with `<` and `>` escaped, so an applicant can't close the tag and write "outside" it. The system prompt says the content is untrusted and must be flagged, not obeyed.
2. **Deterministic pre-scan** (`guardrails.py`). Regexes catch phrases like "ignore your rubric", "system note" and "score of 100". A hit is logged, and a trusted note from our code (outside the envelope) tells the model.
3. **Policy gate on every decision.** Before any action runs, the code checks that:
   - the candidate was scored first;
   - the score equals the sum of a capped breakdown, so "100" needs 40/20/20/20 justified line by line;
   - the action matches the score band (≥70 advance, 40–69 more info, <40 reject);
   - the `candidate_id` matches the application under review;
   - only one decision is made per candidate.

   A violation goes back to the model as an error `tool_result`, so it can correct itself.
4. **No auto-advance for flagged applications.** If the pre-scan or the model flags an application, `advance_to_interview` is held as `pending_human_review`. A manipulated review can't move anyone forward without a person seeing it.
5. **Fail closed.** If the model refuses, runs out of turns or never decides, the candidate goes to `pending_human_review`. The code never guesses.

`tests/test_guardrails.py` simulates a model that obeys C's injection (it scores 100 and advances) and asserts that the advancement is held.

## Design notes and trade-offs

- **The model judges, code enforces.** The LLM reads messy free text, builds the rubric breakdown and writes the questions. The code owns the score-to-action mapping and the state changes, which keeps behaviour predictable and auditable.
- **Score bands are strict.** That makes decisions consistent. The downside is that a borderline 39 versus 40 can flip the outcome. In practice, every rejection already gets a human check.
- **The regex pre-scan is crude.** It gives false positives (a candidate quoting "you are now..." in a cover letter) and false negatives (paraphrased or non-English injections). That's acceptable here because a hit only escalates to a human. It never rejects anyone.
- Uses `claude-opus-5-5` with server-side refusal fallbacks (`fallbacks: "default"`). Tool choice is `auto` with `strict` schemas, because forced tool choice isn't supported on this model; the prompt plus the policy gate drive the tool order instead.

## What I'd do next

- A small human-in-the-loop CLI to approve or overturn queued rejections and held advancements, where a recruiter reviews the decisions the agent isn't allowed to finalise on its own.

   Breaking down:
   - Human-in-the-loop: a person makes the final call on the risky decisions.
   - CLI: command-line interface, a program you run in the terminal (no website needed).
   - Approve: confirm the agent's proposal, so the rejection becomes final.
   - Overturn: disagree and pick a different outcome, such as moving C to "request more info".


- An eval set (about 30 labelled applications) to evaluate the agent decisions and measure agreement with human recruiters.

- Real integrations like automatic email sends behind the same tool interface.
