# SRL Chat

SRL Chat is a conversational AI interview tool for assessing self-regulated learning (SRL) strategies of students. It guides learners through a structured interview, detects strategies across study contexts, asks for frequency ratings, and generates a personalised summary.

The interview protocol is based on Zimmerman & Martinez-Pons' Self-Regulated Learning Interview Schedule.

> Zimmerman, B. J., & Martinez-Pons, M. M. (1986). Development of a Structured Interview for Assessing Student Use of Self-Regulated Learning Strategies. American Educational Research Journal, 23(4), 614-628. https://doi.org/10.2307/1163093

## Features

- **Structured multi-step interview flow** (intro, strategy detection, frequency rating, summary)
  - Bilingual support (German/English)
  - Protocol editor for configuring interview steps
- **Data Collection**
  - Persistent storage of conversation turns, detected strategies, and frequency ratings
  - Activity logging for user interactions and navigation, includinh mopuse traces, character inputs, clicks
  - (optional) Integrated SRL-O survey flow
- **Learning Strategy Detection**
  - RAG-based strategy detection using pgvector and Ollama embeddings (optional, `USE_RAG_STRATEGY=true`)
- **Dashboards**
  - Researcher and teacher dashboards with student results view
- **Compliance**
  - Informed consent flow before interview start
- **Deployment modes**
  - Stand-alone web app
  - LTI tool (e.g., Moodle)
  - Docker Compose stack
  - Discord bot integration for notifications (optional)

## Minimum System Requirements (LLM Server Excluded)

These values cover only SRL Chat services (frontend build/static delivery, Flask backend, PostgreSQL), assuming the LLM inference server is provided separately.

| Scenario                    | Concurrent students | CPU    | RAM   | Disk      | GPU          |
| --------------------------- | ------------------- | ------ | ----- | --------- | ------------ |
| Pilot                       | up to 15            | 2 vCPU | 4 GB  | 20 GB SSD | Not required |
| Course rollout              | 15-50               | 4 vCPU | 8 GB  | 40 GB SSD | Not required |
| Multi-course / campus pilot | 50-120              | 8 vCPU | 16 GB | 80 GB SSD | Not required |

Notes:

- Database growth is mostly from logs and conversation history. Plan +20-50 GB/year for active usage with detailed logging.
- For reliability with dozens of parallel users, run PostgreSQL on dedicated storage and enable backups.

## Quick Start Paths

Detailed technical documentation is in [README-technical.md](README-technical.md).

### 1) Stand-alone mode

1. Install backend and frontend dependencies.
2. Configure environment variables.
3. Initialize and seed database.
4. Build frontend and run backend.

```bash
# backend
cd backend
poetry install
cp ../env.example .env
poetry run python -m app.database.setup_no_embed

# frontend
cd ../frontend
npm install
npm run build

# run API
cd ../backend
poetry run python main.py
```

Open: http://localhost:5000

### 2) LTI mode (Moodle etc.)

Use the same backend setup as stand-alone, then configure your LMS external tool:

- Tool URL: https://<your-host>/lti/launch
- Consumer key / shared secret: values configured in your LMS + SRL Chat

A complete LTI checklist is available in [README-LTI.md](README-LTI.md) and [README-technical.md](README-technical.md).

### 3) Docker Compose

```bash
cp env.example .env
# edit .env values

# development
docker compose -f develop.docker-compose.yml up postgres-dev api-dev

# production-like
# docker compose build --no-cache
# docker compose up -d
```

## Related Software

- tba.

## Citation

```
@software{Seidel2026-SRLAgentSoftware,
  author = {Seidel, Niels and Wetchy, Elisabeth and Radovic, Slavisa and Tiwari, Prasoon and Emsilkh, Abdulrouf},
  title = {SRL-Agent [Software]},
  url = {https://doi.org/10.17605/OSF.IO/KVTXD },
  doi = {10.17605/OSF.IO/KVTXD },
  version = {1.0.0},
  date = {2026-06-12},
}


```

## Research articles and datasets about SRL Chat

Peer-reviewed papers:

- Radović, S., Seidel, N., & Wetchy, E. (2025). Implementing the self-regulated learning structured interview protocol with generative AI: A novel approach for evaluating students’ SRL skills. Journal of Research on Technology in Education, 1–18. https://doi.org/10.1080/15391523.2025.2547176
- Radovic, S., Wetchy, E., & Seidel, N. (2025). An AI-based Chat Agent for Measuring Students’ Self-Regulated Learning Skills. 2025 International Conference on Education Technology and Computers (ICETC)}, 169–173. https://doi.org/10.1109/ICETC66579.2025.11387673
- tba.

## Contributors

- Niels Seidel (project lead)
- Elisabeth Wetchy
- Slavisa Radovic
- Prasoon Tiwari
- Abdulrouf Emsilkh

## License

See [LICENSE.txt](LICENSE.txt).
