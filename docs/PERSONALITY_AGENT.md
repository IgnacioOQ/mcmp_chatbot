# Personality Agent Skill
- status: active
- type: agent_skill
- owner: dev-1
- context_dependencies: {"guide": "chatbot_personality_guide_gemini.md", "conventions": "MD_CONVENTIONS.md"}
<!-- content -->
This agent skill defines how to create, refine, and maintain chatbot personality configurations using Markdown files.

## Purpose
- status: active
- type: context
<!-- content -->
The Personality Agent can:
1. **Create** new personality files from requirements
2. **Refine** personalities based on user feedback
3. **Audit** personalities for completeness

## Architecture: Personality + Context
- status: active
- type: context
<!-- content -->

> [!IMPORTANT]
> Personality files contain only **static** content. Dynamic context (date, retrieved docs, graph data) is injected at runtime by the engine.

| Component | Type | Where |
|-----------|------|-------|
| **Personality** | Static | `prompts/personality.md` |
| **Context** | Dynamic | Injected in `engine.py` |

**Composition flow:**
```
┌────────────────────────────┐
│  prompts/personality.md   │  ← Static (editable without code)
│  - Identity, Tone, Rules  │
└────────────┬───────────────┘
             │ load_personality()
             ▼
┌────────────────────────────┐
│  engine.py: compose prompt │  ← Dynamic (per request)
│  + Date, Graph, Documents │
└────────────┬───────────────┘
             ▼
        system_instruction → LLM
```

**Never put dynamic data in personality files** (e.g., "today is January 29"). The engine handles this.

## Workflow
- status: active
- type: protocol
<!-- content -->
Follow these steps when working with personalities:

### 1. Gather Requirements
- status: active
<!-- content -->
Before creating a personality, understand:
- **Audience**: Who interacts with the chatbot?
- **Domain**: What topics is it expert in?
- **Tone**: Formal, friendly, scholarly, casual?
- **Constraints**: What must it avoid?

### 2. Create Personality Files
- status: active
<!-- content -->

#### Single File (Simple)
Create `prompts/personality.md`:
```markdown
# [Chatbot Name]
- status: active
- type: context
<!-- content -->

## Identity
Name, role, affiliation

## Tone & Style
Key adjectives (precise, warm, scholarly)

## Behavioral Guidelines
Numbered rules for responses

## What to Avoid
Explicit prohibitions
```

#### Modular (Complex)
Split into `prompts/`:
- `base_identity.md` – Core traits
- `domain_expertise.md` – Subject matter
- `response_style.md` – Formatting
- `guardrails.md` – Safety boundaries

### 3. Test and Iterate
- status: active
<!-- content -->
1. Run test queries covering typical questions
2. Evaluate responses against personality spec
3. Identify tone inconsistencies or guideline violations
4. Refine with more specific instructions
5. Document iterations: `<!-- v2: Added warmth, reduced verbosity -->`

## Best Practices
- status: active
- type: guideline
<!-- content -->

| Practice | Bad | Good |
|----------|-----|------|
| Specificity | "Be helpful" | "Address the user's underlying goal" |
| Examples | None | Show correct vs incorrect responses |
| Priority | Implicit | "Safety > Accuracy > Helpfulness" |

## Integration Checklist
- status: active
- type: task
<!-- content -->
- [ ] Create `prompts/` directory
- [ ] Write personality file(s) following schema
- [ ] Implement `load_personality()` in code
- [ ] Pass content as `system_instruction` to LLM
- [ ] Test with varied inputs
- [ ] Iterate based on feedback

## Example: Leopold (MCMP Assistant)
- status: active
- type: context
<!-- content -->

The MCMP chatbot "Leopold" demonstrates effective personality design:

```markdown
# Leopold — MCMP Philosophy Assistant

## Identity
- **Name**: Leopold
- **Character**: Intelligent and helpful, with the efficient precision 
  of someone working in German public administration
- **Affiliation**: Ludwig-Maximilians-Universität München

## Tone & Style
- **Efficient and precise**: Like a knowledgeable German civil servant
- **Politely formal**: Respectful without being stiff
- **Thorough**: Provide complete, well-organized information
```

**Key techniques used:**
| Technique | Example |
|-----------|---------|
| Give a name | "Leopold" creates identity |
| Character archetype | "German public administrator" → efficient, precise |
| Positive framing of traits | "efficient, not rigid" |
| Contrast what to do vs avoid | "thorough" vs "don't be bureaucratic" |

## Tips from Implementation
- status: active
- type: guideline
<!-- content -->

1. **Names matter**: A named persona ("Leopold") feels more consistent than "the assistant"
2. **Use archetypes**: "German civil servant" immediately evokes precision, thoroughness, formality
3. **Add positive constraints**: "Politely formal" guides tone better than "be professional"
4. **Balance warmth and rigor**: Academic credibility + approachability
5. **MD_CONVENTIONS compliance**: Personality files should follow the schema for consistency
