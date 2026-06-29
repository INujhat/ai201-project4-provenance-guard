# Provenance Guard Planning

## Detection Signals

This system uses two detection signals:

### Signal 1: LLM-based classification
This signal asks a Groq Llama model to estimate whether the submitted text appears AI-generated or human-written. It captures overall writing style, coherence, generic phrasing, and patterns that may be difficult to measure with simple rules.

Output: a score from 0.0 to 1.0, where 1.0 means more likely AI-generated and 0.0 means more likely human-written.

Blind spot: LLMs can be wrong, especially with polished human writing or edited AI writing.

### Signal 2: Stylometric heuristics
This signal measures structural writing patterns such as sentence length variation, vocabulary diversity, and punctuation density. AI writing often has smoother, more uniform sentence structure, while human writing can be more irregular.

Output: a score from 0.0 to 1.0, where 1.0 means more likely AI-generated and 0.0 means more likely human-written.

Blind spot: formal human writing may look AI-like, and casual AI writing may look human-like.

## Confidence Scoring

The final AI-likelihood score combines both signals:

- LLM score weight: 60%
- Stylometric score weight: 40%

Formula:

final_score = (llm_score * 0.6) + (style_score * 0.4)

Thresholds:

- 0.80 to 1.00 = likely_ai
- 0.40 to 0.79 = uncertain
- 0.00 to 0.39 = likely_human

A score around 0.50 means the system is unsure and should avoid making a strong claim. Since false positives can harm human creators, the system only labels content as likely AI when confidence is high.

## Transparency Labels

| Result | Exact Label Text |
|---|---|
| High-confidence AI | "Likely AI-generated. Our system has high confidence that this content may have been generated using AI. Because AI detection can be imperfect, creators may appeal this decision." |
| High-confidence human | "Likely human-written. Our system has high confidence that this content appears to have been written by a human." |
| Uncertain | "Uncertain. The system could not confidently determine whether this content is AI-generated or human-written. No strong attribution claim should be made." |

## Appeals Workflow

A creator can submit an appeal if they believe their content was misclassified.

The appeal requires:

- content_id
- creator_reasoning

When an appeal is submitted, the system:

1. Finds the original classification decision.
2. Updates the content status to under_review.
3. Logs the appeal reasoning with the original decision.
4. Returns a confirmation response.

A human reviewer would see the original text, signal scores, final score, label, creator ID, and creator reasoning.

## Edge Cases

1. A formal academic paragraph written by a human may score as AI-generated because it is polished and uniform.
2. A short poem may be difficult to classify because there may not be enough text for reliable stylometric analysis.
3. A non-native English speaker's writing may look unusual to the detector and could be misclassified.
4. Lightly edited AI text may receive an uncertain score because it has both AI-like and human-like traits.

## Architecture

```text
Submission Flow:

User
  |
  v
POST /submit
  |
  v
Validate JSON input: text + creator_id
  |
  v
Signal 1: Groq LLM classification
  |
  v
Signal 2: Stylometric heuristic scoring
  |
  v
Confidence scoring
  |
  v
Transparency label generation
  |
  v
Structured audit log
  |
  v
JSON response with content_id, attribution, confidence, and label


Appeal Flow:

Creator
  |
  v
POST /appeal
  |
  v
Validate content_id + creator_reasoning
  |
  v
Find original decision
  |
  v
Update status to under_review
  |
  v
Write appeal to audit log
  |
  v
JSON confirmation response