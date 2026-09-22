Albatta. Bu feedback aslida **“sizlar loyiha qurdingizlar, endi uni professional darajaga olib chiqinglar”** degani.

Men buni boshidan, juda sodda qilib, **nima bor → nima yetishmayapti → nima qilish kerak → Thursday demo qanday ishlashi kerak** tarzida maydalab tushuntiraman.

---

# 1. Avval umuman nima bo'lyapti?

Sizlarning hozirgi holatingiz taxminan shunday:

```text
Developer
   ↓
Kod yozadi
   ↓
Backend / ML / Frontend
   ↓
GitHub
   ↓
Server
   ↓
Docker
   ↓
Ishlaydigan project
```

Lekin team lead sizlardan keyingi bosqichni kutyapti:

```text
Developer
   ↓
Professional project structure
   ├── Documentation
   ├── Agent rules
   ├── Skills
   ├── Tools
   ├── AI Agent
   ├── CI/CD
   ├── Staging
   └── Production
```

Va eng muhimi:

```text
Real application
       ↓
      Ask
       ↓
      Agent
       ↓
      Tool
       ↓
Real data / real action
       ↓
     Result
```

Ya'ni AI shunchaki ChatGPT bo'lib o'tirmaydi.

U **sizlarning project ichidagi agent** bo'ladi.

---

# 2. Birinchi project nima?

Sizlar ko'rsatgan birinchi project:

> Game-server health / anomaly detection system

Oddiy qilib:

**Counter-Strike serverlarini kuzatadigan sistema.**

Masalan server:

```text
Server 1
Players: 20
Ping: 45ms
Status: Online
```

Keyin birdan:

```text
Ping: 300ms
Players: 5
Packet loss: high
```

Sistema:

> Bu normal emas.

deydi.

Bu **anomaly detection**.

Keyin ML model:

> Nima sabab bo'lishi mumkin?

degan savolga yordam beradi.

Masalan:

```text
Anomaly:
High latency

Possible root cause:
Network issue
```

Siz yuborgan feedback bo'yicha stack taxminan:

```text
FastAPI
PostgreSQL / TimescaleDB
Scikit-learn
Docker Compose
Telegram
```

ML tarafida:

```text
Random Forest
Gradient Boosting
Logistic Regression
```

ishlatilgan.

---

# 3. Ikkinchi project nima?

Ikkinchisi:

> Marketplace review intelligence system

Bu esa product review'larni analiz qiladi.

Masalan:

```text
"This phone has an amazing camera,
but battery life is terrible."
```

Sistema buni ajratishi mumkin:

```text
Sentiment:
Mixed

Aspect:
Camera → Positive
Battery → Negative
```

Keyin root-cause analysis:

```text
Why is the customer unhappy?

Possible reason:
Battery drains quickly.
```

Yana product nomi review ichida yo'q bo'lsa, agent review'dan qaysi product haqida gap ketayotganini taxmin qilishi mumkin.

---

# 4. Lekin team leadning asosiy muammosi projectning o'zi emas

Feedbackning eng muhim qismi shu:

> Development process is relatively informal.

Bu juda muhim.

Ya'ni sizlarda kod bor, AI ishlatilmoqda, roadmap bor.

Lekin:

```text
Qanday kod yozamiz?
Qanday architecture bo'ladi?
Agent nimani biladi?
Agent nimani qila oladi?
Qaysi faylni o'zgartirishi mumkin?
Testing qoidasi nima?
Deployment qanday?
Developer qanday ishlaydi?
```

degan narsalar **yozma va standartlashtirilmagan**.

Shuning uchun ular:

> "Documentation qilinglar."

deyapti.

---

# 5. Documentation nima?

Documentation — projectni boshqa developerga berib:

> "Mana repository. Projectni tushunib ol."

desang, u tushuna oladigan hujjatlar.

Masalan projectga yangi developer keldi.

U:

> Backendni qanday run qilaman?

deydi.

Documentationda:

```text
1. Clone repository
2. Create .env
3. Install dependencies
4. Start PostgreSQL
5. Start Redis
6. Run backend
```

bo'ladi.

Yoki:

> Architecture qanday?

Documentationda:

```text
Frontend
   ↓
API
   ↓
Service
   ↓
Database
```

bo'ladi.

---

# 6. /docs nima?

Feedback:

> Create a real /docs structure

deyapti.

Masalan repository:

```text
project/
│
├── app/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── AGENTS.md
├── README.md
│
└── docs/
    ├── architecture.md
    ├── setup.md
    ├── development.md
    ├── deployment.md
    ├── api.md
    ├── database.md
    ├── ml.md
    └── agents.md
```

Bu shunchaki fayllar ko'paytirish degani emas.

Har birining vazifasi bor.

### architecture.md

Project qanday tuzilgan?

Masalan:

```text
Frontend
    ↓
FastAPI
    ↓
Services
    ↓
PostgreSQL
```

### setup.md

Local computerda qanday ishga tushiramiz?

### development.md

Developer project bilan qanday ishlaydi?

Masalan:

```text
feature branch
    ↓
pull request
    ↓
tests
    ↓
review
    ↓
merge
```

### deployment.md

Serverga qanday deploy qilamiz?

```text
GitHub
   ↓
CI/CD
   ↓
Staging
   ↓
Production
```

### api.md

Endpointlar:

```text
GET /servers
GET /servers/{id}
GET /anomalies
POST /events
```

va request/response formatlari.

### ml.md

ML model nima qiladi?

Masalan:

```text
Input
 ↓
Feature processing
 ↓
Model
 ↓
Prediction
```

### agents.md

AI agent qanday ishlaydi?

Bu juda muhim.

---

# 7. AGENTS.md nima?

Mana feedbackdagi eng muhim narsalardan biri.

```text
AGENTS.md
```

Bu AI coding agentga beriladigan **project qoidalari**.

Tasavvur qiling, jamoaga yangi programmer keldi.

Siz unga aytasiz:

> Biz FastAPI ishlatamiz.
> SQLAlchemy ishlatamiz.
> Service layerdan foydalanamiz.
> Testsiz PR merge qilinmaydi.
> Secretlarni kodga yozma.
> Database schema'ni tasdiqsiz o'zgartirma.

AGENTS.md ham xuddi shuni **AI agentga** aytadi.

---

# 8. Nega AGENTS.md kerak?

Hozir developer Claude yoki boshqa coding agentga:

> "Add authentication."

desa agent o'zicha qaror qabul qiladi.

Lekin agent project qoidalarini bilmasligi mumkin.

Masalan agent:

```text
new architecture
```

qilib yuborishi mumkin.

Yoki:

```text
database model
```

ni noto'g'ri joyga qo'yishi mumkin.

AGENTS.md agentga:

> "Bu projectda shunday ishlaysan."

deydi.

Masalan:

```text
# Project Rules

## Architecture

Use service/repository pattern.

## Backend

Use FastAPI.

## Database

Use PostgreSQL.

## Testing

Every new endpoint must have tests.

## Security

Never expose secrets.

## Changes

Do not modify database schema without migration.
```

Bu faqat oddiy misol.

---

# 9. "Agent instructions" degani nima?

Agent instructions = AI ga berilgan **ishlash qoidalari**.

Masalan:

```text
You are a backend engineering agent.

You must:
- follow project architecture
- use existing services
- write tests
- avoid unnecessary dependencies
- never modify production configuration
```

Bu bilan agentning behavior'i boshqariladi.

---

# 10. Skills nima?

Feedbackda:

> Research and implement “skills.”

deyilgan.

Bu joyi ko'pchilik uchun chalkash.

**Skill — agentning ma'lum bir vazifani qanday bajarishini biladigan reusable capability/instruction set.**

Masalan backend skill:

```text
Backend Development Skill
```

unda:

```text
How to create endpoint
How to validate request
How to handle errors
How to write tests
How to access database
```

kabi qoidalar bo'lishi mumkin.

Testing skill:

```text
Testing Skill
```

unda:

```text
How to create test
What to test
How to run tests
How to verify API
```

Deployment skill:

```text
Deployment Skill
```

unda:

```text
Docker
CI/CD
environment
logs
health checks
rollback
```

borishi mumkin.

---

# 11. Skill bilan AGENTS.md farqi nima?

Bu juda muhim.

### AGENTS.md

**Project-specific rules.**

Ya'ni:

> "Bizning projectimiz qanday ishlaydi?"

### Skill

**Reusable capability.**

Ya'ni:

> "Bu vazifani qanday bajarish kerak?"

Misol:

```text
AGENTS.md
    ↓
"This project uses FastAPI + PostgreSQL."
```

Skill:

```text
Backend API Skill
    ↓
"How to implement FastAPI endpoints correctly."
```

Shunday tasavvur qiling:

```text
AGENTS.md
= Company/project constitution

Skill
= Specialist knowledge
```

---

# 12. Sizlarda nechta skill kerak?

Feedback bo'yicha ko'p emas.

Masalan boshlanishiga:

```text
backend
testing
deployment
```

yetishi mumkin.

Yoki:

```text
backend
architecture
testing
```

.

Maqsad:

> 100 ta skill yig'ish emas.

Maqsad:

> 2–5 ta foydali skillni olib, real projectga ishlatish.

---

# 13. "Faqat research qilmanglar" nimani anglatadi?

Bu juda muhim.

Sizlar prezentatsiya qilib:

> Skills nima?
> Harness nima?
> Agent nima?

deb tushuntirsangiz, bu yetarli emas.

Team lead:

> "Show me working implementation."

deyapti.

Ya'ni:

```text
Research
   ↓
Implement
   ↓
Run
   ↓
Demo
```

kerak.

---

# 14. Agent harness nima?

Feedbackdagi eng qiziq qism shu.

> Learn the concept of an agent harness.

Oddiy qilib:

**Agent harness — AI agent ishlashi uchun kerak bo'lgan butun muhit.**

Agentning o'zi:

```text
LLM
```

xolos.

Lekin real agentga:

```text
LLM
+
Instructions
+
Context
+
Tools
+
Skills
+
Permissions
+
Memory/state
+
Application data
```

kerak bo'ladi.

Mana shu ecosystem:

**Agent Harness**

deb qaraladi.

---

# 15. Eng oddiy misol

Oddiy ChatGPT:

```text
User:
What is the average latency?
```

LLM:

> "Maybe 70ms."

Nega?

Chunki u database'ni ko'rmadi.

Bu **grounded answer emas**.

Sizning projectda esa:

```text
User
 ↓
Agent
 ↓
Tool: get_average_latency()
 ↓
Database
 ↓
72.4 ms
 ↓
Agent
 ↓
"Average latency is 72.4 ms."
```

Mana bu haqiqiy agent.

---

# 16. Nega Tool kerak?

Agentning o'zi databasega tegmasligi mumkin.

Shuning uchun siz unga **tools** berasiz.

Masalan:

```text
get_server_status
get_average_latency
get_anomalies
get_daily_stats
create_event
send_test_notification
```

Agent kerak bo'lganda tool chaqiradi.

---

# 17. Tool qanday ishlaydi?

Masalan user:

> "What is the average latency today?"

Agent ko'radi:

```text
I need today's latency.
```

Keyin:

```text
Tool:
get_average_latency(date=today)
```

Backend:

```text
SELECT AVG(latency)
FROM server_metrics
WHERE date = today
```

Database:

```text
72.4
```

Agent:

> "Today's average latency is 72.4 ms."

Bu juda muhim.

Agent javobni **o'ylab topmayapti**.

U:

```text
LLM
 ↓
Tool
 ↓
Real data
 ↓
Answer
```

qilyapti.

---

# 18. Feedbackdagi "Ask side panel" nima?

Bu UI'dagi kichkina AI oynasi.

Masalan dashboard:

```text
┌──────────────────────────────┐
│ Server Dashboard             │
│                              │
│ Online: 128                  │
│ Offline: 4                   │
│ Avg latency: 72ms            │
│                              │
│                    [ Ask AI ]│
└──────────────────────────────┘
```

User:

> What is the average latency?

Agent:

> Today's average latency is 72.4 ms.

---

# 19. "Summarize what is happening on the dashboard"

Bu ham juda yaxshi demo.

Dashboardda:

```text
120 servers online
5 offline
3 anomalies
average latency 71ms
```

User:

> Summarize the dashboard.

Agent tools orqali:

```text
get_dashboard_summary()
```

chaqiradi.

Tool:

```json
{
  "online": 120,
  "offline": 5,
  "anomalies": 3,
  "avg_latency": 71
}
```

Agent:

> There are 120 online servers and 5 offline servers. Three anomalies were detected, while average latency is 71 ms.

Bu **application-aware AI**.

---

# 20. Eng muhim qism: Agent action qilishi kerak

Feedback:

> Give the agent at least one real action.

Bu savolga javob berishdan ham muhim.

Hozir:

```text
User
 ↓
Question
 ↓
Agent
 ↓
Answer
```

bo'lishi mumkin.

Lekin ular:

```text
User
 ↓
Request
 ↓
Agent
 ↓
Tool
 ↓
Action
 ↓
Result
```

ko'rishni xohlashyapti.

---

# 21. Action nima bo'lishi mumkin?

Feedback o'zi misollar bergan:

```text
create/update an event
trigger a test action
generate/send local email
```

Sizlarga murakkab action shart emas.

Masalan eng xavfsiz demo:

### Create test event

User:

> Create a test event called "High latency test".

Agent:

```text
create_event(
    name="High latency test"
)
```

Backend databasega yozadi:

```text
event_id: 101
name: High latency test
```

Agent:

> Event created successfully.

Dashboardda:

```text
New event
High latency test
```

ko'rinadi.

Mana bu juda yaxshi demo.

---

# 22. Bu yerda "LLM → Tool → Action → Result" nima?

To'liq chain:

```text
USER
  │
  │ "Create a test event"
  ↓
AGENT / LLM
  │
  │ decides to call tool
  ↓
TOOL
  │
  │ create_event()
  ↓
BACKEND
  │
  │ INSERT INTO events
  ↓
DATABASE
  │
  │ success
  ↓
TOOL RESULT
  │
  ↓
AGENT
  │
  ↓
USER
"Event created successfully."
```

Thursday demo aynan shuni ko'rsatishi kerak.

---

# 23. Agent databasega to'g'ridan-to'g'ri SQL yozsinmi?

Men bunday architecture'dan qochishni tavsiya qilaman.

Yaxshiroq:

```text
Agent
 ↓
Approved Tool
 ↓
Backend Service
 ↓
Database
```

emas:

```text
Agent
 ↓
Raw SQL
 ↓
Database
```

Sababi xavfsizlik va control.

Agentga faqat ruxsat berilgan operationlarni berasiz.

Masalan:

```text
get_average_latency
get_server_status
create_test_event
```

Agent:

```text
DROP TABLE servers
```

qila olmaydi, chunki bunday tool yo'q.

Bu **tool permissions** g'oyasi.

---

# 24. Agentga qanday qilib "knowledge" beriladi?

Harness ichida:

```text
Agent
├── Instructions
├── Context
├── Skills
├── Tools
└── Permissions
```

bo'ladi.

Masalan Instructions:

```text
You are the monitoring assistant.
```

Context:

```text
Project uses FastAPI, PostgreSQL and TimescaleDB.
```

Tools:

```text
get_server_status()
get_average_latency()
create_test_event()
```

Skills:

```text
monitoring skill
backend skill
```

Permissions:

```text
Read:
servers
metrics
anomalies

Write:
events

Forbidden:
users
production config
database schema
```

Bu allaqachon kichik harness.

---

# 25. "Domain-specific ChatGPT" degani nima?

Feedbackda:

> essentially a small domain-specific ChatGPT for their system.

degan.

Masalan ChatGPT:

```text
General knowledge
```

Sizlarning agent:

```text
Game server monitoring knowledge
+
your database
+
your APIs
+
your tools
```

bilan ishlaydi.

Shuning uchun u faqat:

> "Python nima?"

degan savolga emas.

Balki:

> "Why did server 42 become unstable?"

degan savolga projectdagi real data orqali javob beradi.

---

# 26. CI/CD nima?

Hozir sizlarda deployment:

```text
GitHub
 ↓
clone
 ↓
Docker
 ↓
configuration
 ↓
server
```

ko'rinishida.

Bu manual deployment.

Ya'ni developer:

```bash
git pull
docker compose up
```

kabi ishlarni o'zi qiladi.

---

# 27. CI/CD nima qiladi?

CI:

**Continuous Integration**

Har safar code push/PR bo'lganda:

```text
code
 ↓
build
 ↓
test
 ↓
lint
```

tekshiradi.

CD:

**Continuous Delivery/Deployment**

Testdan o'tgan code:

```text
GitHub
 ↓
CI
 ↓
Deploy
```

qilishi mumkin.

---

# 28. Nega staging va production kerak?

Hozir:

```text
Developer
   ↓
Production
```

qilish xavfli.

Developer bug qildi:

```text
production broken
```

Shuning uchun:

```text
Development
      ↓
   Staging
      ↓
 Production
```

bo'ladi.

### Development

Developer ishlaydigan environment.

### Staging

Production'ga o'xshash test environment.

### Production

Real userlar ishlatadigan environment.

---

# 29. Branchlar qanday bo'lishi mumkin?

Masalan:

```text
main
```

→ production

```text
develop
```

→ staging

Feature:

```text
feature/agent-tools
```

Developer ishlaydi:

```text
feature/agent-tools
        ↓
      PR
        ↓
    develop
        ↓
    staging
```

hammasi yaxshi bo'lsa:

```text
develop
   ↓
  PR
   ↓
 main
   ↓
production
```

Bu faqat mumkin bo'lgan model; team leadning existing Git workflow'i bilan moslashtirish kerak.

---

# 30. Thursday Definition of Done nimani anglatadi?

Feedbackning eng muhim sentence'i:

> User opens app → opens Ask → asks a question about real application data → agent calls a tool → returns grounded result → user asks it to perform an action → agent executes it → result is visible.

Buni birma-bir ko'ramiz.

---

## Step 1

User applicationni ochadi.

```text
Dashboard
```

---

## Step 2

User:

```text
Ask
```

panelni ochadi.

---

## Step 3

User savol beradi:

```text
What is the average latency today?
```

---

## Step 4

Agent o'zi biladigan toolni tanlaydi:

```text
get_average_latency()
```

---

## Step 5

Backend real database'dan ma'lumot oladi.

Masalan:

```text
72.4 ms
```

---

## Step 6

Agent resultni userga beradi:

```text
Today's average latency is 72.4 ms.
```

Muhim:

Bu answer database'dan olingan.

Bu:

```text
LLM guessed 72ms
```

emas.

---

# 31. Keyingi qism

User:

> Create a test event named "Latency Check".

Agent:

```text
create_event(...)
```

chaqiradi.

Backend:

```text
INSERT INTO events ...
```

qiladi.

Database:

```text
event created
```

qaytaradi.

Agent:

> The test event was created successfully.

---

# 32. Va eng oxirida user ko'radi

Dashboard refresh bo'ladi yoki real-time update keladi:

```text
Events

Latency Check
Created just now
```

Mana shu paytda team lead:

> "Yes, this is a working agent."

deyishi mumkin.

---

# 33. Ular aslida nimani tekshirmoqchi?

Feedbackga qaraganda, ular sizlarning:

```text
AI ishlata olasizmi?
```

degan narsangizni emas, balki:

```text
AI system design qila olasizmi?
```

degan narsani ko'rmoqchi.

Farqi katta.

Oldin:

```text
Developer uses Claude
```

Endi:

```text
Developer designs an agent system
```

---

# 34. Ikki xil AI ishlatish o'rtasidagi farq

### Oldingi model

Siz Claude'ga:

> Build this endpoint.

deysiz.

Claude kod yozadi.

Bu:

```text
AI-assisted development
```

### Yangi model

Siz:

```text
AI agent architecture
```

yaratasiz.

Agentga:

```text
instructions
skills
tools
context
permissions
```

berasiz.

Agent application ichida ishlaydi.

Bu:

```text
Agent-first system
```

g'oyasiga yaqin.

---

# 35. Sizlarning yangi architecture taxminan shunday bo'ladi

```text
                    USER
                      │
                      ▼
                 ASK PANEL
                      │
                      ▼
                 AGENT / LLM
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
       Skills       Context      Rules
          │           │           │
          └───────────┼───────────┘
                      │
                      ▼
                   TOOLS
                ┌─────┴─────┐
                │           │
                ▼           ▼
          Read Tools    Action Tools
                │           │
                ▼           ▼
             Backend     Backend
                │           │
                ▼           ▼
             Database    Database
```

---

# 36. Masalan Tools

Game server project uchun:

```text
get_server()
get_all_servers()
get_average_latency()
get_anomalies()
get_root_cause()
get_dashboard_summary()
```

Action tool:

```text
create_test_event()
```

Keyinchalik:

```text
send_test_notification()
restart_test_monitor()
mark_event_resolved()
```

qo'shilishi mumkin.

Lekin Thursday uchun bittasi yetadi.

---

# 37. "Real application data" juda muhim

Feedbackda aynan:

> asks a question about real application data

deyilgan.

Demak bunday qilish yaxshi emas:

```text
if user asks average latency:
    return random.choice([50,70,90])
```

Bu demo uchun fake response bo'ladi.

Buning o'rniga:

```text
Agent
 ↓
Tool
 ↓
DB query
 ↓
Real metric
```

bo'lishi kerak.

---

# 38. Tool va API bir xilmi?

To'liq bir xil emas.

API:

```text
GET /servers
```

bu application API.

Agent tool:

```text
get_servers()
```

Agent uchun interface.

Uning ichida:

```text
get_servers()
    ↓
GET /servers
```

bo'lishi mumkin.

Yoki tool backend service'ni to'g'ridan-to'g'ri chaqirishi mumkin.

Masalan:

```text
Agent
 ↓
Tool
 ↓
Service
 ↓
Repository
 ↓
DB
```

Bu ham mumkin.

---

# 39. Pydantic bu yerda qayerda keladi?

Sizning oldingi interview project kontekstingizda Pydantic schemas bilan ishlash muhim edi.

Agent tool uchun ham structured schema juda foydali.

Masalan:

```text
create_event
```

uchun:

```text
name: string
description: string
```

kabi input schema bo'ladi.

Agent:

```json
{
  "name": "Latency Check",
  "description": "Test event"
}
```

ko'rinishida structured argument beradi.

Bu:

```text
LLM
 ↓
structured tool call
```

ni ishonchliroq qiladi.

---

# 40. Security masalasi

Bu qismni Thursday demo'da albatta o'ylash kerak.

Agentga:

```text
ALL database access
```

bermang.

Balki:

```text
Read:
metrics
servers
anomalies

Write:
test_events
```

kabi cheklang.

Masalan agentga:

```text
delete production users
```

imkoni bo'lmasligi kerak.

Agent actionlarida authorization bo'lishi kerak.

---

# 41. Documentationda nimani yozish kerak?

Men sizlarga taxminan mana shunday structure tavsiya qilaman:

```text
docs/
│
├── architecture.md
├── setup.md
├── development.md
├── deployment.md
├── api.md
├── database.md
├── ml.md
├── agents.md
├── skills.md
├── tools.md
└── environments.md
```

Har biri:

### architecture.md

System architecture.

### setup.md

Local setup.

### development.md

Development workflow.

### deployment.md

Deployment steps.

### api.md

API endpoints.

### database.md

Tables, relationships, TimescaleDB.

### ml.md

Models and ML pipeline.

### agents.md

Agent architecture.

### skills.md

Available skills and when to use them.

### tools.md

Agent tools and permissions.

### environments.md

Development/staging/production.

---

# 42. AGENTS.md qayerda?

Repository rootida:

```text
project/
├── AGENTS.md
├── README.md
├── docs/
├── backend/
├── frontend/
└── ...
```

Agent repositoryga kirganda shu qoidalarni ko'radi.

---

# 43. AGENTS.md ichida nima bo'lishi mumkin?

Masalan conceptual tarzda:

```text
# Project Agent Instructions

## Project
This is a game-server monitoring system.

## Architecture
FastAPI → Services → PostgreSQL/TimescaleDB.

## Rules
- Follow existing architecture.
- Reuse existing services.
- Do not create duplicate logic.
- Add tests for new functionality.
- Do not expose secrets.

## Database
Use migrations.
Do not directly alter production schema.

## Agent
Agent can read monitoring data.
Agent may create test events.
Agent cannot perform destructive production actions.
```

Bu faqat skeleton.

---

# 44. Skills qanday projectga qo'shiladi?

Masalan:

```text
skills/
├── backend/
│   └── SKILL.md
├── testing/
│   └── SKILL.md
└── deployment/
    └── SKILL.md
```

Backend skill:

```text
When adding an API endpoint:
1. Define schema
2. Define route
3. Use service layer
4. Add validation
5. Add tests
```

Testing:

```text
When code changes:
1. Run unit tests
2. Run integration tests
3. Verify affected endpoints
```

Deployment:

```text
Before deployment:
1. Build Docker image
2. Run tests
3. Verify environment
4. Deploy to staging
```

---

# 45. Nima uchun skills reusable?

Tasavvur qiling frontend project ham bor.

Siz alohida backend skill yaratdingiz.

Keyin boshqa project:

```text
Project A
Project B
Project C
```

hammasida ishlatishingiz mumkin.

Shuning uchun:

> reusable agent skills

deyilmoqda.

---

# 46. CI/CD qanday ko'rinishda bo'lishi mumkin?

Masalan GitHub:

```text
feature branch
      ↓
      PR
      ↓
GitHub Actions
      ↓
Run tests
      ↓
Build
      ↓
Deploy staging
```

Keyin:

```text
staging verified
      ↓
merge main
      ↓
GitHub Actions
      ↓
production deploy
```

---

# 47. Thursday demo uchun butun story

Menimcha eng tushunarli demo story quyidagicha bo'ladi:

### 1

Dashboardni ochasiz.

### 2

Ask panelni ochasiz.

### 3

So'raysiz:

> "What is the average latency today?"

### 4

Agent:

```text
calls get_average_latency
```

### 5

Tool DB'dan:

```text
72.4 ms
```

oladi.

### 6

Agent:

> Today's average latency is 72.4 ms.

### 7

Keyin:

> "Create a test event called Latency Check."

### 8

Agent:

```text
calls create_test_event
```

### 9

Backend event yaratadi.

### 10

Dashboardda yangi event paydo bo'ladi.

### 11

Siz architecture diagramni ko'rsatasiz:

```text
User
 ↓
Ask
 ↓
Agent
 ↓
Tool
 ↓
Backend
 ↓
DB
 ↓
Result
```

### 12

Keyin repositoryni ko'rsatib:

```text
/docs
AGENTS.md
skills/
.github/workflows/
```

ni ko'rsatasiz.

Bu feedbackdagi deyarli barcha talabni bitta demo ichida bog'laydi.

---

# 48. Sizga ayniqsa qaysi qismi backend developer sifatida muhim?

Siz backend tarafda ishlayotgan bo'lsangiz, sizning qismingiz taxminan:

```text
Agent
  ↓
Tool definitions
  ↓
Backend services
  ↓
Database
  ↓
Action execution
```

bo'ladi.

Frontend developer:

```text
Ask panel
Chat UI
Result display
```

qilishi mumkin.

AI developer:

```text
LLM
prompt/instructions
agent orchestration
```

qilishi mumkin.

Lekin boundary oldindan aniq bo'lishi kerak.

---

# 49. Sizlarning backend uchun minimal tool set

Thursday uchun men architecture'ni ataylab kichik tutgan bo'lardim:

```text
1. get_dashboard_summary
2. get_average_latency
3. get_recent_anomalies
4. create_test_event
```

Shu to'rttasi yetadi.

Bunda:

```text
3 ta read operation
+
1 ta write operation
```

bo'ladi.

Bu yaxshi demo balans.

---

# 50. Eng katta xato nima bo'lishi mumkin?

Agentga:

> "Answer anything about the system."

deb qo'yish.

Va tool bo'lmasligi.

Shunda:

```text
LLM
 ↓
guess
```

bo'lishi mumkin.

Ular esa aynan:

```text
LLM
 ↓
tool
 ↓
real system
```

ko'rishni xohlashyapti.

---

# 51. Yana bitta muhim tushuncha: Grounded answer

Feedbackdagi:

> returns grounded result

degani:

**Agent javobni real source'dan oladi.**

Masalan:

```text
"What is average latency?"
```

Agentning o'zi:

> 70ms

deb taxmin qilmaydi.

Tool:

```text
72.4ms
```

qaytaradi.

Agent shu result asosida javob beradi.

Demak:

```text
Grounded = tied to actual application data
```

deb tushunishingiz mumkin.

---

# 52. Oxirida ularning sizlardan kutayotgan narsasi aslida 6 ta asosiy blok

Buni juda qisqa sxema qilib:

```text
1. DOCUMENTATION
        ↓
2. AGENT RULES
        ↓
3. SKILLS
        ↓
4. TOOLS
        ↓
5. MINI AGENT HARNESS
        ↓
6. CI/CD + STAGING/PRODUCTION
```

Va harness ichida:

```text
              Agent
                │
       ┌────────┼────────┐
       ↓        ↓        ↓
    Context  Skills    Tools
                         │
                  ┌──────┴──────┐
                  ↓             ↓
                READ          ACTION
                  ↓             ↓
                 DB           DB/API
```

---

# 53. Buni "oddiy ChatGPT" bilan solishtiring

### Oddiy ChatGPT

```text
User
 ↓
LLM
 ↓
Answer
```

### Sizlarning yangi system

```text
User
 ↓
Application
 ↓
Ask
 ↓
Agent
 ↓
Instructions
 ↓
Skills
 ↓
Tools
 ↓
Real backend
 ↓
Database / API
 ↓
Result
 ↓
Agent
 ↓
User
```

Va kerak bo'lsa:

```text
User
 ↓
Agent
 ↓
Action tool
 ↓
Backend
 ↓
Database
 ↓
UI updated
```

Mana shu **asosiy idea**.

---

# 54. Feedbackni bitta gapga aylantirsak

Team lead sizlarga aslida:

> **"Sizlar AI bilan project yozishni emas, AI agent project ichida qanday ishlashini qurishni o'rganinglar."**

deyapti.

Oldingi bosqich:

```text
AI helps developers
```

Keyingi bosqich:

```text
Developers build systems where AI is a participant
```

Ya'ni agent:

```text
ko'radi
→ tushunadi
→ tool tanlaydi
→ real data oladi
→ action bajaradi
→ result qaytaradi
```

---

## Thursday uchun eng sodda MVP

Sizlar juda katta system qurishingiz shart emas. Mana shu ishlasa, feedbackning asosiy maqsadi ko'rinadi:

```text
Dashboard
   ↓
Ask Panel
   ↓
Agent
   ├── get_average_latency()
   ├── get_dashboard_summary()
   └── create_test_event()
```

Bunga qo'shimcha:

```text
/docs
AGENTS.md
skills/
.github/workflows/
```

va:

```text
staging
production
```

environmentlar.

Shunda sizlarda **research emas, ishlaydigan proof-of-concept** paydo bo'ladi.
