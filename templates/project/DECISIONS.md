# Decisions

Append-only. Newest at the bottom. Never edit or delete an entry: a changed decision is a new entry
that names the one it replaces. Jorah records every decision it takes under the charter's decision
rights; the runner records Adam's answers and applied defaults.

Entry format:

```markdown
## YYYY-MM-DD <short title> (Q-xxxx or T-xxxx if any)

- **Who:** Adam | Jorah, under the charter's decision rights | default (Adam silent by decide_by)
- **Decision:** <what was decided>
- **Why:** <the reason, in a sentence or two>
- **Evidence:** <paths, commit SHAs, URLs>
- **Reversible:** <yes, cheaply | with cost: what | no>
- **Replaces:** <date and title of an earlier entry, or nothing>
```
