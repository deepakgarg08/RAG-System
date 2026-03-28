# Skill: Write an Architecture Decision Record (ADR)

## When to use this skill
Use whenever a significant technical decision is made — choosing a library,
pattern, data format, deployment approach, or any decision with trade-offs.

## Step-by-step process

### 1. Find the next ADR number
Open docs/decisions.md and find the highest existing ADR number. Use next number.

### 2. Write the ADR using this exact template

```markdown
## ADR-00X: [Short title — what was decided]

**Status:** Accepted
**Date:** YYYY-MM-DD
**Decider:** Deepak Garg

### Context
[2-3 sentences: what is the situation, what problem needs solving,
why does a decision need to be made now]

### Decision
[1-2 sentences: exactly what was decided, stated clearly]

### Reasoning
[Bullet points: why this option was chosen over alternatives]
- Reason 1
- Reason 2

### Alternatives Considered
| Option | Why rejected |
|---|---|
| Alternative A | [reason] |
| Alternative B | [reason] |

### Consequences
**Positive:**
- [benefit 1]
- [benefit 2]

**Negative / Trade-offs:**
- [trade-off 1]

### Production Upgrade Path
[How this decision would change when moving to Riverty production Azure environment]
```

### 3. Append to docs/decisions.md
Add the new ADR at the bottom of docs/decisions.md separated by `---`.
