# Provenance Guard

Provenance Guard is a Flask backend system that analyzes submitted text and returns an attribution result, confidence score, transparency label, and audit log entry. It also supports creator appeals and rate limiting.

## Architecture Overview

A user submits text through `POST /submit`. The system validates the input, runs two detection signals, combines the scores into one confidence score, generates a reader-facing transparency label, writes the decision to `audit_log.json`, and returns a structured JSON response.

Appeals use `POST /appeal`. The creator submits a `content_id` and reasoning. The system updates the content status to `under_review` and logs the appeal.

## Detection Signals

### Signal 1: Groq LLM classification

This signal uses Groq's Llama model to estimate whether the text appears AI-generated or human-written.

It captures broad writing patterns, generic phrasing, structure, and overall style.

Blind spot: polished human writing or edited AI writing can confuse the model.

### Signal 2: Stylometric heuristics

This signal measures sentence length variation, vocabulary diversity, and punctuation density.

AI writing can be more uniform, while human writing often has more irregular structure.

Blind spot: formal human writing may look AI-like, and casual AI writing may look human-like.

## Confidence Scoring

Both signals return a score from `0.0` to `1.0`.

- `0.0` = more likely human-written
- `1.0` = more likely AI-generated

Final score:

```text
final_score = (llm_score * 0.6) + (style_score * 0.4)