from __future__ import annotations

from app.db import get_store
from app.models.contracts import (
    AgentCatalogItem,
    ExecutionPlan,
    HumanApproval,
    KanbanBoard,
    PlanTask,
    Project,
    RequirementSpecification,
    TaskCard,
)
from app.models.enums import (
    ApprovalDecision,
    ApprovalType,
    AutonomyLevel,
    CardType,
    KanbanColumn,
    Priority,
)

CORE_AGENTS = [
    AgentCatalogItem(
        id="supervisor",
        name="Nova",
        role="supervisor",
        description="Robot supervisor that owns the delivery flow end-to-end",
        preferred_model="grok-3-mini",
        tools=["chat", "kanban", "approvals"],
        autonomy_level=AutonomyLevel.OPERACAO,
        success_rate=0.94,
    ),
    AgentCatalogItem(
        id="triagem",
        name="Scout",
        role="triagem",
        description="Classifies each software demand and spots missing inputs",
        tools=["classify"],
        success_rate=0.96,
    ),
    AgentCatalogItem(
        id="requisitos",
        name="Spec",
        role="requisitos",
        description="Writes requirements and testable acceptance criteria",
        tools=["docs"],
        success_rate=0.91,
    ),
    AgentCatalogItem(
        id="planejador",
        name="Map",
        role="planejador",
        description="Breaks software builds into executable swarm tasks",
        tools=["planning"],
        success_rate=0.9,
    ),
    AgentCatalogItem(
        id="arquiteto",
        name="Atlas",
        role="arquiteto",
        description="Designs components and interfaces for mini-apps",
        preferred_model="grok-3-mini",
        tools=["architecture"],
        success_rate=0.88,
    ),
    AgentCatalogItem(
        id="coordenador",
        name="Hive",
        role="coordenador",
        description="Forms the hierarchical swarm and assigns robot specialists",
        tools=["swarm"],
        autonomy_level=AutonomyLevel.INTEGRACAO,
        success_rate=0.92,
    ),
    AgentCatalogItem(
        id="desenvolvedor",
        name="Forge",
        role="desenvolvedor",
        description="Builds complete mini-apps and deploys a live preview",
        tools=["git", "editor", "runtime"],
        autonomy_level=AutonomyLevel.INTEGRACAO,
        success_rate=0.86,
        avg_cost_tokens=45_000,
    ),
    AgentCatalogItem(
        id="testador",
        name="Pulse",
        role="testador",
        description="Runs acceptance checks against the generated software",
        tools=["tests"],
        success_rate=0.89,
    ),
    AgentCatalogItem(
        id="revisor",
        name="Lens",
        role="revisor",
        description="Independent review of quality and requirement fit",
        tools=["review"],
        success_rate=0.93,
    ),
    AgentCatalogItem(
        id="documentacao",
        name="Quill",
        role="documentacao",
        description="Publishes delivery notes and usage docs",
        tools=["docs"],
        success_rate=0.95,
    ),
    AgentCatalogItem(
        id="chamados",
        name="Beacon",
        role="chamados",
        description="Opens blockers and incidents when agents get stuck",
        tools=["tickets"],
        success_rate=0.97,
    ),
]

# Specialty blueprints used to mint hundreds of English example robots.
_SPECIALTY_BLUEPRINTS: list[dict] = [
    {
        "role": "frontend",
        "family": "Frontend",
        "names": [
            "Pixel", "Canvas", "Glow", "Frame", "Vista", "Spark", "Aura", "Prism",
            "Bloom", "Shade", "Glyph", "Orbit", "Flare", "Crest", "Drift", "Lumen",
            "Tessera", "Halo", "Ripple", "Sable", "Nimbus", "Velvet", "Cobalt", "Iris",
        ],
        "focus": [
            "React", "Vue", "Svelte", "Next.js", "Tailwind", "accessibility", "motion",
            "design systems", "responsive layouts", "CSS architecture", "component libraries",
            "micro-frontends", "Storybook", "forms UX", "data tables", "charts",
            "dark mode", "i18n UI", "PWA shells", "landing pages",
        ],
        "tools": ["editor", "browser", "figma", "css"],
        "models": ["gpt-4.1-mini", "grok-3-mini", "claude-sonnet"],
        "autonomy": AutonomyLevel.IMPLEMENTACAO,
        "tokens": (14_000, 32_000),
    },
    {
        "role": "backend",
        "family": "Backend",
        "names": [
            "Bolt", "Relay", "Kernel", "Stack", "Vector", "Cipher", "Node", "Pulse",
            "Anchor", "Forge", "Rail", "Summit", "Core", "Bridge", "Flux", "Delta",
            "Harbor", "Quartz", "Vertex", "Axiom", "Nexus", "Cascade", "Helix", "Ion",
        ],
        "focus": [
            "REST APIs", "GraphQL", "gRPC", "auth services", "rate limiting", "caching",
            "PostgreSQL", "MongoDB", "Redis", "message queues", "webhooks", "file uploads",
            "background jobs", "API versioning", "OpenAPI", "session stores",
            "multi-tenant APIs", "search indexes", "billing hooks", "feature flags",
        ],
        "tools": ["editor", "runtime", "db", "http"],
        "models": ["gpt-4.1-mini", "gpt-4.1", "grok-3-mini"],
        "autonomy": AutonomyLevel.INTEGRACAO,
        "tokens": (18_000, 48_000),
    },
    {
        "role": "fullstack",
        "family": "Full-stack",
        "names": [
            "Summit", "Cascade", "Meridian", "Apex", "Unity", "Arc", "Compass", "Stride",
            "Pioneer", "Trail", "Link", "Span", "Voyage", "Beacon", "Pathfinder", "Ranger",
            "Atlas", "Keystone", "Horizon", "Polaris", "Waypoint", "Circuit", "Ledger", "Prime",
        ],
        "focus": [
            "CRUD apps", "admin dashboards", "SaaS MVPs", "auth + UI", "CRUD + deploy",
            "marketplace prototypes", "booking flows", "inventory tools", "CRM shells",
            "content portals", "survey builders", "kanban clones", "chat widgets",
            "file managers", "billing demos", "team workspaces", "onboarding flows",
            "notification hubs", "settings centers", "profile suites",
        ],
        "tools": ["git", "editor", "runtime", "db"],
        "models": ["gpt-4.1", "grok-3-mini", "claude-sonnet"],
        "autonomy": AutonomyLevel.INTEGRACAO,
        "tokens": (28_000, 55_000),
    },
    {
        "role": "mobile",
        "family": "Mobile",
        "names": [
            "Swift", "Pocket", "Touch", "Nova", "Pulse", "Glide", "Tap", "Wave",
            "Signal", "Roam", "Nest", "Flick", "Dash", "Sprite", "Beacon", "Orbit",
            "Comet", "Zip", "Nomad", "Drift", "Echo", "Spark", "Flux", "Rune",
        ],
        "focus": [
            "React Native", "Flutter", "Expo apps", "offline sync", "push notifications",
            "camera flows", "maps UX", "biometric login", "app navigation", "deep links",
            "store listing copy", "adaptive layouts", "gesture UX", "mobile forms",
            "native modules", "performance profiling", "crash triage", "A/B mobile UX",
            "onboarding carousels", "wallet-style UIs",
        ],
        "tools": ["editor", "simulator", "device"],
        "models": ["gpt-4.1-mini", "claude-sonnet"],
        "autonomy": AutonomyLevel.IMPLEMENTACAO,
        "tokens": (20_000, 42_000),
    },
    {
        "role": "qa",
        "family": "QA",
        "names": [
            "Probe", "Check", "Guard", "Verify", "Sentry", "Audit", "Proof", "Gauge",
            "Inspect", "Trace", "Scout", "Radar", "Canary", "Witness", "Assay", "Metric",
            "Validator", "Sentinel", "Monitor", "Falcon", "Lynx", "Owl", "Hawk", "Argus",
        ],
        "focus": [
            "unit tests", "integration suites", "E2E Playwright", "visual regression",
            "load testing", "fuzzing", "contract tests", "accessibility audits",
            "smoke packs", "regression triage", "flaky-test hunting", "coverage gaps",
            "API assertions", "snapshot hygiene", "chaos drills", "release gates",
            "browser matrix", "mobile device farms", "perf budgets", "security smoke",
        ],
        "tools": ["tests", "browser", "ci"],
        "models": ["gpt-4.1-mini", "grok-3-mini"],
        "autonomy": AutonomyLevel.IMPLEMENTACAO,
        "tokens": (10_000, 28_000),
    },
    {
        "role": "security",
        "family": "Security",
        "names": [
            "Shield", "Vault", "Cipher", "Aegis", "Lock", "Ward", "Bastion", "Fence",
            "Iron", "Bulwark", "Keeper", "Gate", "Seal", "Fort", "Watch", "Phantom",
            "Spectre", "Raven", "Warden", "Paladin", "Knight", "Castle", "Harbor", "Safe",
        ],
        "focus": [
            "OWASP reviews", "auth hardening", "secrets scanning", "dependency CVEs",
            "threat modeling", "input validation", "CORS policy", "CSP headers",
            "JWT hygiene", "RBAC audits", "SSRF checks", "SQL injection hunts",
            "XSS defenses", "supply-chain risk", "pen-test notes", "privacy reviews",
            "logging redaction", "secure defaults", "crypto usage", "session fixation",
        ],
        "tools": ["review", "scanner", "docs"],
        "models": ["gpt-4.1", "claude-sonnet"],
        "autonomy": AutonomyLevel.PLANEJAMENTO,
        "tokens": (12_000, 30_000),
    },
    {
        "role": "devops",
        "family": "DevOps",
        "names": [
            "Pipeline", "Harbor", "Rocket", "Dock", "Cloud", "Launch", "Relay", "Gear",
            "Crane", "Tower", "Engine", "Turbine", "Reactor", "Orbit", "Stage", "Ship",
            "Anchor", "Helm", "Warp", "Boost", "Ignite", "Payload", "Carrier", "Fleet",
        ],
        "focus": [
            "CI/CD", "Docker builds", "Kubernetes", "preview deploys", "CDN setup",
            "blue-green releases", "infra as code", "secrets rotation", "log pipelines",
            "metrics dashboards", "alerting rules", "cost controls", "rollback playbooks",
            "env promotion", "artifact registries", "CDN cache purge", "TLS certs",
            "autoscaling", "health probes", "multi-region failover",
        ],
        "tools": ["ci", "runtime", "cloud", "git"],
        "models": ["gpt-4.1-mini", "grok-3-mini"],
        "autonomy": AutonomyLevel.OPERACAO,
        "tokens": (16_000, 40_000),
    },
    {
        "role": "data",
        "family": "Data",
        "names": [
            "Lattice", "Prism", "Cube", "Signal", "Query", "Index", "Stream", "Metric",
            "Ledger", "Corpus", "Tableau", "Vector", "Column", "Spark", "Lake", "Shard",
            "Pivot", "Sigma", "Nova", "Pulse", "Drift", "Sample", "Tensor", "Graph",
        ],
        "focus": [
            "ETL pipelines", "SQL modeling", "analytics dashboards", "event schemas",
            "data quality", "warehouse loads", "feature stores", "A/B metrics",
            "cohort analysis", "CSV ingest", "parquet transforms", "anomaly detection",
            "reporting APIs", "BI embeds", "retention policies", "PII tagging",
            "lineage maps", "slow-query tuning", "embedding indexes", "time-series stores",
        ],
        "tools": ["db", "sql", "notebook"],
        "models": ["gpt-4.1", "grok-3-mini"],
        "autonomy": AutonomyLevel.IMPLEMENTACAO,
        "tokens": (15_000, 38_000),
    },
    {
        "role": "ml",
        "family": "ML",
        "names": [
            "Neuron", "Model", "Inference", "Prompt", "Embed", "Sage", "Oracle", "Muse",
            "Cortex", "Synapse", "Token", "Bayes", "Ada", "Claude", "Grok", "Echo",
            "Mind", "Vision", "Whisper", "Reason", "Planner", "Critic", "Router", "Judge",
        ],
        "focus": [
            "prompt engineering", "RAG pipelines", "embedding search", "eval harnesses",
            "classification models", "summarization", "tool-calling agents", "guardrails",
            "fine-tune plans", "dataset curation", "hallucination checks", "routing LLMs",
            "vision OCR", "speech-to-text", "recommendation stubs", "anomaly models",
            "cost/latency tradeoffs", "offline evals", "online feedback loops", "agent memory",
        ],
        "tools": ["notebook", "runtime", "eval"],
        "models": ["gpt-4.1", "claude-sonnet", "grok-3-mini"],
        "autonomy": AutonomyLevel.PLANEJAMENTO,
        "tokens": (22_000, 50_000),
    },
    {
        "role": "design",
        "family": "Design",
        "names": [
            "Muse", "Palette", "Sketch", "Form", "Craft", "Studio", "Ink", "Grid",
            "Type", "Mood", "Layout", "Icon", "Tone", "Shape", "Rhythm", "Balance",
            "Contrast", "Space", "Flow", "Mark", "Brand", "Story", "Gaze", "Focus",
        ],
        "focus": [
            "UI kits", "token systems", "wireframes", "user flows", "visual hierarchy",
            "empty states", "icon sets", "illustration briefs", "brand voice",
            "prototype polish", "interaction patterns", "responsive grids", "color contrast",
            "typography scales", "component variants", "marketing pages", "onboarding art",
            "error screens", "dashboard density", "motion specs",
        ],
        "tools": ["figma", "docs", "browser"],
        "models": ["gpt-4.1-mini", "claude-sonnet"],
        "autonomy": AutonomyLevel.PLANEJAMENTO,
        "tokens": (8_000, 22_000),
    },
    {
        "role": "docs",
        "family": "Docs",
        "names": [
            "Quill", "Scroll", "Manual", "Guide", "Index", "Brief", "Memo", "Chronicle",
            "Archive", "Lexicon", "Primer", "Handbook", "Digest", "Outline", "Synopsis",
            "Capsule", "Leaflet", "Codex", "Annals", "Record", "Note", "Script", "Verse", "Prose",
        ],
        "focus": [
            "API references", "README polish", "runbooks", "changelog drafting",
            "onboarding guides", "architecture ADRs", "release notes", "FAQ pages",
            "SDK samples", "migration guides", "troubleshooting trees", "glossary work",
            "internal wikis", "customer help centers", "security whitepapers",
            "status page copy", "demo scripts", "tutorial series", "CLI help text", "RFC drafts",
        ],
        "tools": ["docs", "git"],
        "models": ["gpt-4.1-mini", "grok-3-mini"],
        "autonomy": AutonomyLevel.ANALISE,
        "tokens": (6_000, 18_000),
    },
    {
        "role": "support",
        "family": "Support",
        "names": [
            "Helpdesk", "Ally", "Care", "Assist", "Relay", "Concierge", "Companion", "Guide",
            "Advocate", "Liaison", "Porter", "Steward", "Host", "Buddy", "Mentor", "Coach",
            "Counsel", "Helper", "Responder", "Triage", "Desk", "Inbox", "Ticket", "Rescue",
        ],
        "focus": [
            "incident intake", "customer replies", "escalation routing", "SLA tracking",
            "bug reproduction", "status updates", "knowledge base hits", "chat macros",
            "refund workflows", "account recovery", "onboarding help", "feature education",
            "outage comms", "priority ranking", "sentiment triage", "follow-up loops",
            "handoff notes", "VIP queues", "community answers", "feedback synthesis",
        ],
        "tools": ["tickets", "chat", "docs"],
        "models": ["gpt-4.1-mini", "grok-3-mini"],
        "autonomy": AutonomyLevel.ANALISE,
        "tokens": (5_000, 16_000),
    },
    {
        "role": "product",
        "family": "Product",
        "names": [
            "North", "Scope", "Roadmap", "Insight", "Pulse", "Discovery", "Outcome", "Goal",
            "Metric", "Lean", "Sprint", "Backlog", "Hypothesis", "Signal", "Priority", "Value",
            "Journey", "Persona", "Opportunity", "Bet", "Experiment", "Impact", "Focus", "Theme",
        ],
        "focus": [
            "problem framing", "user stories", "PRD drafts", "success metrics",
            "competitive scans", "prioritization", "experiment design", "roadmap cuts",
            "stakeholder briefs", "MVP scoping", "acceptance reviews", "release themes",
            "pricing notes", "onboarding goals", "retention levers", "activation funnels",
            "churn signals", "feature scoring", "opportunity sizing", "go-to-market briefs",
        ],
        "tools": ["docs", "planning", "chat"],
        "models": ["gpt-4.1", "claude-sonnet"],
        "autonomy": AutonomyLevel.PLANEJAMENTO,
        "tokens": (9_000, 24_000),
    },
    {
        "role": "research",
        "family": "Research",
        "names": [
            "Lumen", "Quest", "Probe", "Survey", "Field", "Lab", "Insight", "Finder",
            "Seeker", "Oracle", "Archive", "Scholar", "Theory", "Sample", "Study", "Lens",
            "Radar", "Scan", "Deepdive", "Explorer", "Cartographer", "Analyst", "Scribe", "Sage",
        ],
        "focus": [
            "user interviews", "competitive intel", "literature scans", "technology bets",
            "benchmarking", "market sizing", "prototype tests", "heuristic reviews",
            "journey maps", "pain-point mining", "trend briefs", "patent-style notes",
            "feasibility studies", "vendor comparisons", "API landscape scans",
            "risk registers", "assumption tests", "synthesis memos", "evidence packs", "R&D spikes",
        ],
        "tools": ["docs", "browser", "notebook"],
        "models": ["gpt-4.1", "claude-sonnet"],
        "autonomy": AutonomyLevel.ANALISE,
        "tokens": (11_000, 26_000),
    },
    {
        "role": "performance",
        "family": "Performance",
        "names": [
            "Turbo", "Swift", "Boost", "Racer", "Sprint", "Flash", "Throttle", "Nitro",
            "Warp", "Zoom", "Velocity", "Amp", "Overdrive", "Dash", "Blaze", "Jet",
            "Rocket", "Pulse", "Stride", "Pace", "Tempo", "Rush", "Snap", "Fastlane",
        ],
        "focus": [
            "bundle analysis", "lazy loading", "image optimization", "cache headers",
            "database indexes", "N+1 queries", "cold-start cuts", "CDN tuning",
            "Web Vitals", "memory leaks", "CPU profiling", "render thrashing",
            "SSR hydration", "worker offload", "connection pooling", "payload shrink",
            "streaming responses", "edge caching", "font loading", "third-party audits",
        ],
        "tools": ["profiler", "browser", "runtime"],
        "models": ["gpt-4.1-mini", "grok-3-mini"],
        "autonomy": AutonomyLevel.IMPLEMENTACAO,
        "tokens": (12_000, 28_000),
    },
    {
        "role": "integration",
        "family": "Integration",
        "names": [
            "Bridge", "Adaptor", "Sync", "Hook", "Conduit", "Portal", "Gateway", "Link",
            "Weave", "Join", "Mux", "Pipe", "Socket", "Relay", "Hub", "Interface",
            "Connector", "Passport", "Courier", "Messenger", "Channel", "Tunnel", "Span", "Bond",
        ],
        "focus": [
            "Stripe hooks", "Slack bots", "email providers", "OAuth providers",
            "Salesforce sync", "webhook retries", "Zapier-style flows", "calendar APIs",
            "maps SDKs", "payment refunds", "CRM imports", "SSO connectors",
            "shipping APIs", "tax services", "SMS gateways", "analytics SDKs",
            "storage buckets", "identity brokers", "feature-flag vendors", "error trackers",
        ],
        "tools": ["http", "editor", "runtime"],
        "models": ["gpt-4.1-mini", "gpt-4.1"],
        "autonomy": AutonomyLevel.INTEGRACAO,
        "tokens": (14_000, 36_000),
    },
]


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace("+", "plus")
        .replace("/", "-")
        .replace(" ", "-")
        .replace(".", "")
        .replace("'", "")
    )


def build_example_agents(target: int = 250) -> list[AgentCatalogItem]:
    """Mint a large English specialty catalog for demos."""
    agents: list[AgentCatalogItem] = []
    used_ids: set[str] = {a.id for a in CORE_AGENTS}
    used_names: set[str] = {a.name.lower() for a in CORE_AGENTS}

    for blueprint in _SPECIALTY_BLUEPRINTS:
        role = blueprint["role"]
        family = blueprint["family"]
        names: list[str] = blueprint["names"]
        focuses: list[str] = blueprint["focus"]
        tools: list[str] = blueprint["tools"]
        models: list[str] = blueprint["models"]
        autonomy: AutonomyLevel = blueprint["autonomy"]
        token_lo, token_hi = blueprint["tokens"]

        for index, focus in enumerate(focuses):
            if len(agents) >= target:
                break
            name_base = names[index % len(names)]
            name = name_base if name_base.lower() not in used_names else f"{name_base} {family[:3]}"
            used_names.add(name.lower())

            focus_slug = _slug(focus)[:28]
            agent_id = f"{role}_{focus_slug}"
            if agent_id in used_ids:
                agent_id = f"{role}_{focus_slug}_{index + 1}"
            used_ids.add(agent_id)

            model = models[index % len(models)]
            success = round(0.82 + ((index * 7 + len(role) * 3) % 15) / 100, 2)
            avg_tokens = token_lo + ((index * 1379) % max(1, token_hi - token_lo))
            # Sprinkle a few inactive demo robots.
            active = (index + len(role)) % 17 != 0

            agents.append(
                AgentCatalogItem(
                    id=agent_id,
                    name=name,
                    role=role,
                    description=f"{family} specialist for {focus}. Ships reliable English-ready deliverables for swarm missions.",
                    preferred_model=model,
                    tools=list(tools),
                    autonomy_level=autonomy,
                    active=active,
                    success_rate=min(success, 0.98),
                    avg_cost_tokens=avg_tokens,
                    version="1.0.0",
                )
            )
        if len(agents) >= target:
            break

    # Top up with numbered variants if blueprints alone are short of the target.
    ordinal = 1
    while len(agents) < target:
        blueprint = _SPECIALTY_BLUEPRINTS[ordinal % len(_SPECIALTY_BLUEPRINTS)]
        role = blueprint["role"]
        family = blueprint["family"]
        focus = blueprint["focus"][ordinal % len(blueprint["focus"])]
        name = f"{blueprint['names'][ordinal % len(blueprint['names'])]}-{ordinal:03d}"
        agent_id = f"{role}_unit_{ordinal:03d}"
        if agent_id in used_ids:
            ordinal += 1
            continue
        used_ids.add(agent_id)
        agents.append(
            AgentCatalogItem(
                id=agent_id,
                name=name,
                role=role,
                description=f"{family} unit #{ordinal:03d} focused on {focus}. Ready for parallel swarm assignments.",
                preferred_model=blueprint["models"][ordinal % len(blueprint["models"])],
                tools=list(blueprint["tools"]),
                autonomy_level=blueprint["autonomy"],
                active=ordinal % 19 != 0,
                success_rate=round(0.84 + (ordinal % 12) / 100, 2),
                avg_cost_tokens=blueprint["tokens"][0] + (ordinal * 211) % 20_000,
            )
        )
        ordinal += 1

    return agents


MVP_AGENTS = CORE_AGENTS + build_example_agents(250)


async def seed_if_empty() -> dict:
    store = get_store()
    existing = await store.list("projects")
    if existing:
        project = Project.model_validate(existing[0])
        boards = await store.list("kanban_boards", {"project_id": project.id})
        board = KanbanBoard.model_validate(boards[0]) if boards else None
        # always refresh agent catalog for demo consistency
        for agent in MVP_AGENTS:
            await store.upsert("agents", agent)
        return {"project_id": project.id, "board_id": board.id if board else None, "seeded": False}

    project = Project(
        id="proj_demo",
        name="Swarm Software Factory",
        description="Board for shipping complete mini-apps with robot agents",
        default_autonomy=AutonomyLevel.IMPLEMENTACAO,
    )
    board = KanbanBoard(
        id="board_demo",
        project_id=project.id,
        name="Delivery Board",
    )
    await store.upsert("projects", project)
    await store.upsert("kanban_boards", board)

    for agent in MVP_AGENTS:
        await store.upsert("agents", agent)

    demo_cards = [
        TaskCard(
            id="card_seed_1",
            title="Todo Mini App",
            description="Build a complete Todo web app with add/complete/delete and local persistence. Deploy a live preview.",
            type=CardType.NOVA_FUNCIONALIDADE,
            project_id=project.id,
            board_id=board.id,
            priority=Priority.ALTA,
            column=KanbanColumn.EM_EXECUCAO,
            tags=["mini-app", "frontend"],
            acceptance_criteria=["Add/complete/delete todos", "Persist locally", "Live preview URL"],
            agents=["coordenador", "desenvolvedor", "testador"],
            subtasks=["UI", "State", "Deploy preview"],
            budget_spent=38_000,
            requester="product",
            human_owner="product_owner",
        ),
        TaskCard(
            id="card_seed_2",
            title="Notes Pad",
            description="Blocked while waiting for design tokens for the Notes mini-app.",
            type=CardType.NOVA_FUNCIONALIDADE,
            project_id=project.id,
            board_id=board.id,
            priority=Priority.MEDIA,
            column=KanbanColumn.BLOQUEADO,
            tags=["mini-app", "blocked"],
            acceptance_criteria=["Create/edit notes", "Search", "Live preview"],
            agents=["desenvolvedor", "chamados"],
            block_reason="Waiting on brand color tokens from design",
            budget_spent=12_000,
        ),
        TaskCard(
            id="card_seed_3",
            title="Pomodoro Timer",
            description="Complete Pomodoro timer shipped by the swarm.",
            type=CardType.NOVA_FUNCIONALIDADE,
            project_id=project.id,
            board_id=board.id,
            priority=Priority.MEDIA,
            column=KanbanColumn.CONCLUIDO,
            tags=["mini-app", "live"],
            acceptance_criteria=["Start/pause/reset", "Session history", "Deployed preview"],
            agents=["desenvolvedor", "revisor", "documentacao"],
            budget_spent=8_500,
            runtime_status="stopped",
        ),
        TaskCard(
            id="card_seed_4",
            title="Bookmark Board",
            description="Build a bookmark manager with tags and filters. Ready for human approval before swarm build.",
            type=CardType.NOVA_FUNCIONALIDADE,
            project_id=project.id,
            board_id=board.id,
            priority=Priority.ALTA,
            column=KanbanColumn.AGUARDANDO_APROVACAO,
            tags=["mini-app", "approval"],
            acceptance_criteria=[
                "Save links with titles/tags",
                "Filter by tag",
                "Live preview deployed by Forge",
            ],
            agents=["requisitos", "arquiteto", "desenvolvedor"],
            subtasks=["Wireframes", "UI", "Deploy"],
        ),
    ]
    for card in demo_cards:
        await store.upsert("task_cards", card)

    await store.upsert(
        "requirements",
        RequirementSpecification(
            card_id="card_seed_4",
            objective="Ship a complete Bookmark Board mini-app",
            context="Users want a fast personal bookmark manager with tags.",
            functional=[
                "Save bookmarks with title, URL, and tags",
                "Filter bookmarks by tag",
                "Persist data locally",
            ],
            non_functional=["Modern responsive UI", "Loads under 2s"],
            business_rules=["URLs must be valid"],
            constraints=["Single-user local app"],
            acceptance_criteria=[
                "Save links with titles/tags",
                "Filter by tag",
                "Live preview deployed by Forge",
            ],
        ),
    )
    await store.upsert(
        "execution_plans",
        ExecutionPlan(
            card_id="card_seed_4",
            objective="Bookmark Board",
            strategy="Static mini-app first, then deploy live preview",
            tasks=[
                PlanTask(title="Define data model", agent_role="requisitos"),
                PlanTask(title="Build UI", agent_role="desenvolvedor", parallel_group=1),
                PlanTask(title="Deploy preview", agent_role="desenvolvedor", parallel_group=1),
            ],
            required_agents=["requisitos", "arquiteto", "desenvolvedor", "testador"],
            completion_criteria=[
                "Save links with titles/tags",
                "Filter by tag",
                "Live preview deployed by Forge",
            ],
        ),
    )
    await store.upsert(
        "approvals",
        HumanApproval(
            card_id="card_seed_4",
            type=ApprovalType.ESCOPO,
            requester="supervisor",
            decision=ApprovalDecision.PENDENTE,
            comment="Scope ready: approve to let the robot swarm build and deploy the mini-app.",
        ),
    )

    return {"project_id": project.id, "board_id": board.id, "seeded": True}
