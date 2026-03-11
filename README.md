# trading-bot

Live/paper trading execution engine with risk management and monitoring.

## Tech Stack
- **Go 1.23+** with `gorilla/websocket`, `gRPC`, `Gin`, `Redis`
- Calls Python strategy service via gRPC
- Deployed with **Docker Compose**

## Quick Start
```bash
# Paper trading
docker compose up

# Or run directly
go run ./cmd/bot/ --config config/paper.yaml
```

## Architecture
```
Go Bot ←→ Python Strategy Service (gRPC)
  ↓
Exchange WebSocket (real-time data)
  ↓
Risk Manager → Order Executor → Exchange REST API
  ↓
Redis (state) + Telegram (alerts) + FastAPI (dashboard)
```
