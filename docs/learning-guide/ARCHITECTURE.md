# Architecture

![Architecture diagram](architecture.svg)

## Diagram as Mermaid (GitHub draws this automatically)

```mermaid
flowchart TB
  main["main.py<br/>reads one line"] --> router["router.py<br/>hands requests on"]
  router --> planner["task_planner.py<br/>plans: rules or AI"]
  planner --> skills["skills.py<br/>runs approved actions"]
  planner --> ai
  skills --> ai["ai.py<br/>chat and planning<br/>grounded Gemini search<br/>inert proposal drafts"]
  config["config.py<br/>apps, sites, model settings"] --> ai
  ai -. "proposal, not run" .-> dev["skill_development.py<br/>validates, stores, never runs"]
  dev --> store[("skill_proposals/<br/>untrusted proposals and audit")]

  classDef plumbing fill:#F1EFE8,stroke:#5F5E5A,color:#444441
  classDef acts fill:#E1F5EE,stroke:#0F6E56,color:#085041
  classDef aiside fill:#EEEDFE,stroke:#534AB7,color:#3C3489
  class main,router,config,store plumbing
  class planner,skills acts
  class ai,dev aiside
```

## What each part does

| File | Job |
|---|---|
| `main.py` | Reads one line of input |
| `router.py` | Hands each request to the task planner |
| `task_planner.py` | Makes a deterministic plan, or asks the AI for a constrained proposal |
| `skills.py` | Performs approved actions, manages notes, and starts bounded research |
| `ai.py` | Chat, planning, grounded Gemini search, and inert proposal generation |
| `skill_development.py` | Validates and stores proposals without running them |
| `skill_proposals/` | Untrusted proposal and audit folder, created when needed |
| `config.py` | App, website, and model settings |
| `tests/` | Mock the AI, web responses, and app launches; no live web requests |

## Assumptions in the diagram (check these)
- `ai.py` passes drafted proposals to `skill_development.py`.
- `config.py` also feeds `skills.py` (apps and websites); only one arrow is drawn to keep the diagram clear.
- `tests/` is not drawn because it takes no part in the runtime flow.
