# Automotive News Aggregator

This project is a FastAPI-based service that scrapes automotive news from multiple sources, groups similar news, and merges them into a single, polished, publication-ready news using OpenAI's GPT-4.1 Mini model. The output includes a headline (max 300 chars), optional subheadline (max 500 chars), news body (2,000–5,000 chars), and metadata (car brand/model). The service runs on a cron schedule (every 30 minutes) and uses a SQL database for storage and Redis for caching.

## Features
- **Web Scraping**: Scrapes automotive news from sources like `auto.economictimes.indiatimes.com`, `autocarindia.com`, and `rushlane.com` using Playwright.
- **News Grouping**: Clusters similar news based on content similarity.
- **AI Processing**: Merges news into a polished output using Groq Llama-3.3-70B-Versatile, with structured format (headline, subheadline, news, metadata).
- **Async Workflow**: Built with FastAPI for efficient, asynchronous processing.
- **Persistence**: Stores news and metadata in a SQL database (via SQLAlchemy) and caches processed groups in Redis.
- **Scheduling**: Runs scraping and processing every 30 minutes using APScheduler.

## Tech Stack
- **Python**: 3.11
- **Framework**: FastAPI
- **Scraping**: Playwright
- **HTTP Client**: `aiohttp`
- **Database**: SQL (via SQLAlchemy)
- **Caching**: Redis
- **Scheduler**: APScheduler
- **AI Model**: OpenAI GPT-4.1 Mini (`gpt-4.1-mini`, $0.40/$1.60 per 1M input/output tokens)
- **Optional Models**: Groq Llama-3.3-70B-Versatile, OpenAI o4-mini, GPT-5 Nano

## Prerequisites
- **Python**: 3.11+
- **Redis**: Installed and running locally or on a server.
- **Database**: A SQL database (e.g., PostgreSQL, MySQL) with SQLAlchemy-compatible driver.
- **API Keys**:
  - OpenAI API key for GPT-4.1 Mini (from `https://platform.openai.com`, if used).
  - Groq API key for Llama-3.3-70B-Versatile (from `https://console.groq.com`, if used).
