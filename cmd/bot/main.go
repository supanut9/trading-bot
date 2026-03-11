package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/supanut9/trading-bot/internal/api"
)

func main() {
	log.Println("Starting Trading Bot in Paper Mode...")

	// 1. Initialize API Server
	apiServer := api.NewAPIServer()
	go func() {
		if err := apiServer.Run(":8081"); err != nil {
			log.Fatalf("API Server failed: %v", err)
		}
	}()

	// 2. Mock WebSocket Data Stream & Metrics Broadcaster
	stopData := make(chan bool)
	go func() {
		ticker := time.NewTicker(2 * time.Second)
		defer ticker.Stop()
		
		equity := 100000.0
		for {
			select {
			case <-ticker.C:
				// Simulate equity movement
				equity += float64((time.Now().Unix() % 10) - 5)
				
				// Broadcast to dashboard
				metric := map[string]interface{}{
					"timestamp": time.Now().Format(time.RFC3339),
					"equity":    equity,
					"symbol":    "BTC/USDT",
					"price":     70000.0 + float64(time.Now().Unix()%100),
				}
				apiServer.BroadcastMetric(metric)
				
			case <-stopData:
				return
			}
		}
	}()

	// 3. Main Event Loop Simulation
	log.Println("Bot is running. Press Ctrl+C to stop.")

	// Wait for termination signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	log.Println("Shutting down gracefully...")
	stopData <- true
	time.Sleep(500 * time.Millisecond)
	log.Println("Bot stopped.")
}
