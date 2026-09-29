# Notes: Gemini Models & Pricing

## Model Choices for ReviewLens

### `gemini-2.5-flash` (Default)
- **Role**: Primary review and verification engine.
- **Context Window**: 1,000,000 tokens.
- **Pricing**:
  - Prompt tokens: $0.075 / 1,000,000 tokens ($0.000000075 / token)
  - Candidate tokens: $0.30 / 1,000,000 tokens ($0.00000030 / token)
- **Typical PR Cost**: Under $0.002 per review.
- **Strengths**: Ultra-fast latency (sub-2s responses), strong structured JSON schema adherence, extremely cost-effective for high-frequency CI pipelines.

### `gemini-2.5-pro` (Alternative)
- **Role**: Complex architectural refactoring or deep reasoning evaluation.
- **Pricing**:
  - Prompt tokens: $1.25 / 1,000,000 tokens
  - Candidate tokens: $5.00 / 1,000,000 tokens
- **Trade-off**: Higher reasoning fidelity at approximately 15x cost and higher latency.
