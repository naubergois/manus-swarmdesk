<p align="center">
  <img src="docs/assets/manus-swarmdesk-icon.png" alt="Manus SwarmDesk icon" width="128" height="128" />
</p>

<h1 align="center">Manus SwarmDesk</h1>

<p align="center">
  <strong>Multi-agent platform for autonomous software delivery, driven by an intelligent Kanban.</strong>
</p>

<p align="center">
  <a href="#english">English</a> ·
  <a href="#中文">中文</a> ·
  <a href="#português">Português</a>
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-0F6A5A" />
  <img alt="Stack" src="https://img.shields.io/badge/stack-React%20%7C%20FastAPI%20%7C%20MongoDB-1c2430" />
  <img alt="MVP" src="https://img.shields.io/badge/status-MVP-d8efe9?color=0F6A5A" />
</p>

---

# English

## What is Manus SwarmDesk?

**Manus SwarmDesk** is a multi-agent software delivery platform. You describe a need in natural language; the system turns it into a Kanban card, refines requirements, asks for human approval, and coordinates a swarm of specialized agents to analyze, plan, implement, review, test, and document the solution.

It combines:

- an intelligent assistant (Manus-style portal)
- an autonomous software factory
- a visual Kanban task manager
- an agent orchestrator
- a ticket / incident hub
- a human approval and audit trail

### Example

> Create an API to register customers, authenticate users, and query orders.

The platform creates a card, classifies it, produces requirements and acceptance criteria, builds an execution plan, waits for approval, forms a swarm, and updates the Kanban as work progresses.

## Architecture

| Layer | Responsibility |
| --- | --- |
| **Experience** | Dashboard, Kanban, Portal chat, Swarm console, Approvals, Tickets, Agents, Projects |
| **Control** | LangGraph orchestrator + LangChain agents, Kanban transitions, approvals, audit |
| **Execution** | Hierarchical swarm (Ruflo-style) with real LLM specialists, artifacts, tests |
| **Contracts** | Pydantic / TypeScript models for every critical exchange |
| **Data** | MongoDB (or in-memory store for local demo), optional Redis |

```text
Portal / Kanban (React)
        │
        ▼
   FastAPI control plane
        │
   ┌────┴────┐
   ▼         ▼
LangGraph   Swarm
  + LLM      agents
   │         │
   └────┬────┘
        ▼
   Mongo / memory store
```

## Screens

| Route | Screen | Purpose |
| --- | --- | --- |
| `/` | Executive dashboard | Running work, blockers, deliveries, cost/tokens, agent performance |
| `/kanban` | Smart Kanban | 13 columns, drag-and-drop, filters, create tasks |
| `/cards/:id` | Card detail | Requirements, plan, agents, artifacts, tests, tickets, history |
| `/portal` | Manus portal | Natural-language intake → card creation |
| `/swarm` | Swarm center | Topology, assignments, progress, errors |
| `/approvals` | Approvals | Scope and delivery human decisions |
| `/tickets` | Tickets | Blockers and support items linked to cards |
| `/agents` | Agent catalog | Activate/deactivate agents, roles, models |
| `/projects` | Projects | Lightweight project / board administration |

## Tech stack

- **Frontend:** Vite, React 19, TypeScript, Tailwind CSS, React Router, `@dnd-kit`, Zustand
- **Backend:** FastAPI, Pydantic v2, Motor (MongoDB)
- **Orchestration:** real **LangGraph** pipeline + **LangChain** agents (Anthropic). Hierarchical swarm follows Ruflo-style topology
- **Infra:** Docker Compose for MongoDB + Redis

## Repository structure

```text
Mankiu/
├── apps/web/                 # React SPA
├── apps/api/                 # FastAPI control plane
├── packages/shared/          # Shared TypeScript contracts
├── docs/assets/              # Brand assets (icon)
├── docker-compose.yml
└── README.md
```

## Prerequisites

- Node.js 20+
- Python **3.12 or 3.13** (3.14 is not recommended for this MVP)
- Optional: Docker for MongoDB / Redis

## Quick start

### 1) API

```bash
cd apps/api
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

By default `USE_MEMORY_STORE=true` (see `apps/api/.env`) so you can run **without MongoDB**.

**Required:** configure at least one LLM key in `apps/api/.env` (see `.env.example`): `XAI_API_KEY`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`. The API auto-selects a provider and fails over on quota errors.

To use MongoDB:

```bash
docker compose up -d
# set USE_MEMORY_STORE=false in apps/api/.env
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2) Web

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite proxy forwards `/api` to `http://localhost:8000`.

### Demo flow

1. Open **Portal** and describe a demand in natural language.
2. The card moves through triage → refinement → **Awaiting approval**.
3. Approve in **Approvals** or in the card detail.
4. The swarm executes (developer → reviewer → tester → docs) until **Ready for delivery**.
5. Approve delivery to mark the card **Completed**.

## Kanban columns

`Backlog intake → AI triage → Refinement → Awaiting approval → Ready for swarm → In execution → In review → In testing → Awaiting decision → Ready for delivery → Completed · Blocked · Cancelled`

## MVP agents

Supervisor, Triage, Requirements, Planner, Architect, Swarm Coordinator, Developer, Tester, Reviewer, Documentation, Tickets.

## Important MVP notes

- Agents call a real LLM (xAI / Gemini / OpenAI / Anthropic) with structured Pydantic outputs. No mock content.
- GitHub / real LLM / RAG integrations are prepared via adapters but not wired for production yet.
- Transition rules enforce acceptance criteria before execution and tests before delivery.

## License

MIT — see repository for details.

---

# 中文

## Manus SwarmDesk 是什么？

**Manus SwarmDesk** 是一个面向软件交付的多智能体平台。你用自然语言描述需求，系统会自动创建看板卡片、完善需求、请求人工审批，并协调一组专业智能体完成分析、规划、实现、评审、测试与文档编写。

它融合了：

- 智能助手门户（类似 Manus）
- 自主软件工厂
- 可视化看板任务管理
- 智能体编排器
- 工单 / 事件中心
- 人工审批与审计轨迹

### 示例

> 创建一个用于注册客户、用户认证和查询订单的 API。

平台会创建卡片、分类、生成需求与验收标准、制定执行计划、等待审批、组建智能体群组，并在看板中实时反映进度。

## 架构

| 层级 | 职责 |
| --- | --- |
| **体验层** | 仪表盘、看板、门户聊天、群组控制台、审批、工单、智能体、项目 |
| **控制层** | LangGraph + LangChain 真实智能体、看板流转、审批、审计 |
| **执行层** | 分层群组（Ruflo 风格）+ 真实 LLM 专家、产物、测试 |
| **契约层** | 关键交换使用 Pydantic / TypeScript 模型 |
| **数据层** | MongoDB（或本地内存演示存储）、可选 Redis |

## 页面

| 路由 | 页面 | 作用 |
| --- | --- | --- |
| `/` | 管理仪表盘 | 执行中任务、阻塞、交付、成本/Token、智能体表现 |
| `/kanban` | 智能看板 | 13 列、拖拽、筛选、创建任务 |
| `/cards/:id` | 卡片详情 | 需求、计划、智能体、产物、测试、工单、历史 |
| `/portal` | Manus 门户 | 自然语言录入 → 创建卡片 |
| `/swarm` | 群组中心 | 拓扑、任务分配、进度、错误 |
| `/approvals` | 审批中心 | 范围与交付的人工决策 |
| `/tickets` | 工单中心 | 与卡片关联的阻塞与支持事项 |
| `/agents` | 智能体目录 | 启用/停用、角色、模型 |
| `/projects` | 项目管理 | 轻量项目 / 看板管理 |

## 技术栈

- **前端：** Vite、React 19、TypeScript、Tailwind CSS、React Router、`@dnd-kit`、Zustand
- **后端：** FastAPI、Pydantic v2、Motor（MongoDB）
- **编排：** 真实 **LangGraph** + **LangChain**（Anthropic）。分层群组采用 Ruflo 风格拓扑
- **基础设施：** Docker Compose（MongoDB + Redis）

## 仓库结构

```text
Mankiu/
├── apps/web/                 # React 单页应用
├── apps/api/                 # FastAPI 控制面
├── packages/shared/          # 共享 TypeScript 契约
├── docs/assets/              # 品牌资源（图标）
├── docker-compose.yml
└── README.md
```

## 环境要求

- Node.js 20+
- Python **3.12 或 3.13**（本 MVP 不建议使用 3.14）
- 可选：Docker（MongoDB / Redis）

## 快速开始

### 1）启动 API

```bash
cd apps/api
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

默认 `USE_MEMORY_STORE=true`，可在**不依赖 MongoDB**的情况下本地运行。

如需 MongoDB：

```bash
docker compose up -d
# 在 apps/api/.env 中设置 USE_MEMORY_STORE=false
```

接口文档：[http://localhost:8000/docs](http://localhost:8000/docs)

### 2）启动前端

```bash
cd apps/web
npm install
npm run dev
```

打开 [http://localhost:5173](http://localhost:5173)。Vite 会将 `/api` 代理到 `http://localhost:8000`。

### 演示流程

1. 打开 **Portal（门户）**，用自然语言描述需求。
2. 卡片依次进入分诊 → 细化 → **等待审批**。
3. 在 **Approvals（审批）** 或卡片详情中批准。
4. 群组执行（开发 → 评审 → 测试 → 文档）直到 **准备交付**。
5. 批准交付后，卡片变为 **已完成**。

## 看板列

`录入 → AI 分诊 → 细化中 → 等待审批 → 准备群组 → 执行中 → 评审中 → 测试中 → 等待决策 → 准备交付 → 已完成 · 已阻塞 · 已取消`

## MVP 智能体

主管、分诊、需求、规划、架构、群组协调、开发、测试、评审、文档、工单。

## MVP 说明

- 智能体通过真实 LLM（xAI / Gemini / OpenAI / Anthropic）生成结构化 Pydantic 输出，无 mock。
- GitHub / 真实大模型 / RAG 等通过适配器预留，尚未接入生产环境。
- 流转规则：进入执行前必须有验收标准；交付前必须有测试结果。

## 许可证

MIT

---

# Português

## O que é o Manus SwarmDesk?

O **Manus SwarmDesk** é uma plataforma multiagente para entrega autônoma de software. Você descreve uma necessidade em linguagem natural; o sistema transforma isso em cartão de Kanban, refina requisitos, pede aprovação humana e coordena um enxame de agentes especializados para analisar, planejar, implementar, revisar, testar e documentar a solução.

Ele combina:

- assistente inteligente (portal no estilo Manus)
- fábrica autônoma de software
- gerenciador visual de tarefas (Kanban)
- orquestrador de agentes
- central de chamados / incidentes
- trilha de aprovação humana e auditoria

### Exemplo

> Criar uma API para cadastrar clientes, autenticar usuários e consultar pedidos.

A plataforma cria o cartão, classifica a demanda, gera requisitos e critérios de aceitação, monta o plano, aguarda aprovação, forma o enxame e atualiza o Kanban conforme o trabalho avança.

## Arquitetura

| Camada | Responsabilidade |
| --- | --- |
| **Experiência** | Dashboard, Kanban, Portal, Enxame, Aprovações, Chamados, Agentes, Projetos |
| **Controle** | Orquestrador LangGraph + agentes LangChain, transições, aprovações, auditoria |
| **Execução** | Enxame hierárquico (estilo Ruflo) com especialistas LLM reais |
| **Contratos** | Modelos Pydantic / TypeScript em toda troca crítica |
| **Dados** | MongoDB (ou store em memória para demo local), Redis opcional |

## Telas

| Rota | Tela | Função |
| --- | --- | --- |
| `/` | Dashboard executivo | Execução, bloqueios, entregas, custo/tokens, desempenho |
| `/kanban` | Kanban inteligente | 13 colunas, drag-and-drop, filtros, criação de tarefas |
| `/cards/:id` | Detalhe do cartão | Requisitos, plano, agentes, artefatos, testes, tickets, histórico |
| `/portal` | Portal Manus | Entrada em linguagem natural → criação de cartão |
| `/swarm` | Central do enxame | Topologia, atribuições, progresso, erros |
| `/approvals` | Aprovações | Decisões humanas de escopo e entrega |
| `/tickets` | Chamados | Bloqueios e suporte vinculados a cartões |
| `/agents` | Catálogo de agentes | Ativar/desativar, papéis, modelos |
| `/projects` | Projetos | Administração leve de projetos / quadros |

## Stack tecnológica

- **Frontend:** Vite, React 19, TypeScript, Tailwind CSS, React Router, `@dnd-kit`, Zustand
- **Backend:** FastAPI, Pydantic v2, Motor (MongoDB)
- **Orquestração:** **LangGraph** + **LangChain** reais (Anthropic). Enxame hierárquico estilo Ruflo
- **Infra:** Docker Compose para MongoDB + Redis

## Estrutura do repositório

```text
Mankiu/
├── apps/web/                 # SPA React
├── apps/api/                 # Plano de controle FastAPI
├── packages/shared/          # Contratos TypeScript compartilhados
├── docs/assets/              # Assets de marca (ícone)
├── docker-compose.yml
└── README.md
```

## Pré-requisitos

- Node.js 20+
- Python **3.12 ou 3.13** (3.14 não é recomendado neste MVP)
- Opcional: Docker para MongoDB / Redis

## Início rápido

### 1) API

```bash
cd apps/api
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Por padrão `USE_MEMORY_STORE=true` (arquivo `apps/api/.env`), permitindo rodar **sem MongoDB**.

Para usar MongoDB:

```bash
docker compose up -d
# defina USE_MEMORY_STORE=false em apps/api/.env
```

Documentação da API: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2) Web

```bash
cd apps/web
npm install
npm run dev
```

Abra [http://localhost:5173](http://localhost:5173). O proxy do Vite encaminha `/api` para `http://localhost:8000`.

### Fluxo demo

1. Abra o **Portal** e descreva uma demanda em linguagem natural.
2. O cartão passa por triagem → refinamento → **Aguardando aprovação**.
3. Aprove em **Aprovações** ou no detalhe do cartão.
4. O enxame executa (dev → revisor → testes → docs) até **Pronto para entrega**.
5. Aprove a entrega para marcar o cartão como **Concluído**.

## Colunas do Kanban

`Entrada → Triagem por IA → Em refinamento → Aguardando aprovação → Pronto para o enxame → Em execução → Em revisão → Em testes → Aguardando decisão → Pronto para entrega → Concluído · Bloqueado · Cancelado`

## Agentes do MVP

Supervisor, Triagem, Requisitos, Planejador, Arquiteto, Coordenador do enxame, Desenvolvedor, Testador, Revisor, Documentação, Chamados.

## Observações importantes do MVP

- Os agentes chamam um LLM real (xAI / Gemini / OpenAI / Anthropic) com saídas Pydantic estruturadas. Sem mock.
- Integrações reais com GitHub / LLM / RAG estão preparadas via adaptadores, mas ainda não em produção.
- As regras de transição exigem critérios de aceitação antes da execução e testes antes da entrega.

## Licença

MIT

---

<p align="center">
  <img src="docs/assets/manus-swarmdesk-icon.png" alt="Manus SwarmDesk" width="64" height="64" />
  <br />
  <sub>Manus SwarmDesk — human control, multi-agent execution, auditable Kanban.</sub>
</p>
