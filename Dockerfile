# Build stage
FROM golang:1.24-bookworm AS builder

WORKDIR /app

# Copy go mod and sum files
COPY go.mod go.sum ./
RUN go mod download

# Copy the rest of the source code
COPY . .

# Build the bot
RUN go build -o bot cmd/bot/main.go

# Final stage
FROM debian:bookworm-slim

WORKDIR /app

# Install certificates for HTTPS/Binance connection
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy the binary from the builder
COPY --from=builder /app/bot .

# Expose API port
EXPOSE 8081

# Command to run the bot
CMD ["./bot"]
