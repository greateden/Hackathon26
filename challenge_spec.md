# Track 2A: OST - Multilingual NLI over Swiss Official Voting Booklets

> Source: https://hackapertus.notion.site/track-2a-ost
> Retrieved: 2026-10-06
> **This file is the authoritative source for task requirements.**

---

## Challenge Overview

- **Domain:** Civic / Democracy

## Context & Background

Switzerland's direct democracy asks citizens to vote several times a year on complex legal, social and financial issues. For each national vote, the federal government publishes an official voting booklet (Abstimmungsbuechlein) explaining the proposal, its background, the arguments of supporters and opponents, and the position of the Federal Council and Parliament.

These materials are a rich source of complex, structured and unstructured information - proposal descriptions, legal and financial detail, arguments, qualifications, dates, numbers and statements across different linguistic contexts - and an authoritative, relatively balanced basis for understanding what is being voted on.

During campaigns, voters meet many claims about proposals, and checking them against the official materials is difficult and time-consuming. This challenge explores how Apertus can be applied to this document-grounded claim-verification task, while remaining multilingual.

## Problem Description

Given an official Swiss voting booklet and a claim, the system must decide whether the document:
- **entails** the claim;
- **contradicts** the claim; or
- is **neutral** - the document does not provide enough information either way.

**Core task:** Document + Claim -> Entailment / Contradiction / Neutral

This is specifically about document extraction and document-grounded NLI using Apertus. Not general QA. Only whether the model can reliably determine the relationship between a claim and the source document.

## Primary Objective

Build a practical, multilingual claim-verification application powered by Apertus. Must demonstrate:
1. How **reliably** Apertus can perform document-grounded NLI
2. How **efficiently** the relevant document context can be provided

A straightforward baseline: provide the complete voting booklet with the claim directly to Apertus. However, voting booklets can contain substantial text and complex structure. Participants are encouraged to investigate whether the document can be processed, selected or compressed before providing to Apertus, while maintaining reliable NLI performance.

The challenge leaves technical approach open. System should handle document-grounded NLI over complex multilingual documents.

---

## Key Resources

### Paper
- "How Good is AI on Swiss Voting Booklets? A Multilingual OCR and Alignment Benchmark"
- Authors: Elina Stussi, Jannis Vamvas (SwissText 2026, pp. 232-242)
- URL: https://aclanthology.org/2026.swisstext-1.22/

### GitHub Repositories
- github.com/Eljuanina/VotingBooklets - Main repo (OCR code, gold_files, alignment experiments)
- github.com/Eljuanina/VotingBooklets-MA - Master thesis (full pipeline + agent experiments)
- github.com/Eljuanina/VotingBooklets-mono - Monolithic pipeline: OCR -> cleaning -> alignment
- github.com/Eljuanina/agentic-corpus-builder - LangChain agentic pipeline

### HuggingFace Datasets (Gated)
- eljuanina/VotingBooklets-v1 - Full aligned corpus
- eljuanina/VotingBooklets-Diamond-v1 - Gold-standard OCR and alignment annotations

### Languages: DE / FR / IT / RM
### Diamond Benchmark Dates: 1977-06-12, 1985-12-01, 2007-03-11

### Pipeline Stages (VotingBooklets-mono)
1. Download - voting booklet PDFs from federal collection
2. OCR Extraction - Pytesseract / Gemini 2.5 Flash Lite
3. OCR Cleaning - remove Unicode artifacts, fix hyphenation
4. Multilingual Alignment - Sentence SwissBERT -> cosine sim -> position-aware DP

### OCR Quality (Gemini 2.5 Flash Lite WER)
- 1977: DE 0.046, FR 0.045, IT 0.032
- 1985: DE 0.012, FR 0.018, IT 0.016, RM 0.017
- 2007: DE 0.035, FR 0.072, IT 0.039, RM 0.057

### Alignment Quality (F1)
- 1977: FR 0.921, IT 0.919
- 1985: FR 0.953, IT 1.000, RM 0.981
- 2007: FR 0.981, IT 0.986, RM 0.953

### Corpus Statistics
| Year | DE Tokens | FR Tokens | IT Tokens | RM Tokens | Paragraphs |
|------|-----------|-----------|-----------|-----------|------------|
| 1977 | 4,016 | 4,997 | 4,492 | - | 209 |
| 1985 | 1,621 | 2,199 | 1,827 | 2,042 | 107 |
| 2007 | 2,017 | 2,612 | 2,431 | 2,785 | 179 |

---

## Our Implementation Plan

Build minimal baseline: claim -> retrieval -> official evidence paragraphs -> judgement + source

### RAG Approach:
1. Ingest: OCR/parse PDFs -> structured text per section
2. Index: Build retrieval index (SwissBERT embeddings)
3. Retrieve: Given a claim, find relevant passages
4. Judge: Feed claim + evidence to Apertus for NLI classification
5. Report: Output entailment/contradiction/neutral + source passage

### Constraints:
- Use local open-source models (Apertus, SwissBERT)
- Prefer RAG over full-document-in-prompt
- Must handle DE/FR/IT/RM
- Provide source evidence for each judgement
- NLI labels: entailment / contradiction / neutral (3-class)

### Environment
- Platform: macOS (darwin)
- HF datasets are gated - need HF token with access
- Apertus: 70B/8B variants, 256k context (gated on HF)
- Sentence SwissBERT: open source for embeddings
