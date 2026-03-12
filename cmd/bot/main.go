package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/supanut9/trading-bot/internal/api"
	"github.com/supanut9/trading-bot/internal/exchange"
	"github.com/supanut9/trading-bot/internal/risk"
	"github.com/supanut9/trading-bot/internal/strategy"
)

func main() {
	log.Println("Starting Trading Bot with Binance Data...")

	symbol := "BTCUSDT" // Binance format
	displaySymbol := "BTC/USDT"

	// 1. Initialize API Server
	apiServer := api.NewAPIServer()
	go func() {
		if err := apiServer.Run(":8081"); err != nil {
			log.Fatalf("API Server failed: %v", err)
		}
	}()

	// 2. Initialize Strategy Client
	stratClient, err := strategy.NewClient("localhost:50051")
	if err != nil {
		log.Fatalf("Failed to connect to Strategy Service: %v", err)
	}
	defer stratClient.Close()
	log.Println("Connected to Strategy Service")

	// 3. Initialize Exchange & Risk
	ex := exchange.NewBinance()
	defer ex.Close()

	rm := risk.NewSimpleRiskManager(0.01) // Max 0.01 BTC per trade

	// 4. State Management
	equity := 100000.0
	currentPrice := 0.0
	// Local position tracking (simplified)
	currentPositionSize := 0.0
	entryPrice := 0.0

	// 5. Data Streams & Strategy Execution
	candleCh, err := ex.WatchCandles(symbol, "1m")
	if err != nil {
		log.Fatalf("Failed to watch candles: %v", err)
	}

	tickerCh, err := ex.WatchTicker(symbol)
	if err != nil {
		log.Fatalf("Failed to watch ticker: %v", err)
	}

	// Handle Ticker (for dashboard & current price)
	go func() {
		for t := range tickerCh {
			currentPrice = t.Price
			
			// Broadcast to dashboard
			metric := map[string]interface{}{
				"timestamp": t.Time.Format(time.RFC3339),
				"equity":    equity,
				"symbol":    displaySymbol,
				"price":     currentPrice,
			}
			apiServer.BroadcastMetric(metric)
		}
	}()

	// Handle Candles (for strategy)
	go func() {
		log.Printf("Listening for 1m candles for %s...", symbol)
		for c := range candleCh {
			log.Printf("Received Closed Candle: O:%f H:%f L:%f C:%f", c.Open, c.High, c.Low, c.Close)
			
			// Call Strategy Service
			resp, err := stratClient.GetSignal(
				displaySymbol,
				c.Close, // current price
				c.Open,
				c.High,
				c.Low,
				c.Close,
				c.Volume,
			)

			if err != nil {
				log.Printf("Strategy Service Error: %v", err)
				continue
			}

			if resp.Side != "NONE" {
				log.Printf("Received Signal: %s %f", resp.Side, resp.Size)
				
				// Validate with Risk Manager
				finalSize, ok := rm.ValidateOrder(symbol, resp.Side, c.Close, resp.Size)
				if !ok {
					log.Printf("Risk Manager rejected order")
					continue
				}

				log.Printf("Executing %s %f %s at %f", resp.Side, finalSize, symbol, c.Close)
				
				// Simple execution simulation (Paper Trading)
				if resp.Side == "BUY" {
					equity -= c.Close * finalSize * 1.0001 // price + 0.01% commission
					currentPositionSize += finalSize
					entryPrice = c.Close
				} else if resp.Side == "SELL" {
					if currentPositionSize > 0 {
						equity += c.Close * finalSize * 0.9999 // price - 0.01% commission
						currentPositionSize -= finalSize
					}
				}

				// Update dashboard positions
				if currentPositionSize != 0 {
					apiServer.SetPositions([]api.Position{
						{Symbol: displaySymbol, Side: "BUY", Size: currentPositionSize, Entry: entryPrice},
					})
				} else {
					apiServer.SetPositions([]api.Position{})
				}
			}
		}
	}()

	// 6. Main Event Loop & Graceful Shutdown
	log.Println("Bot is running. Press Ctrl+C or use Panic Button to stop.")

	// Wait for termination signal or Panic Button
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	select {
	case <-sigChan:
		log.Println("Shutdown signal received...")
	case <-apiServer.PanicCh:
		log.Println("Panic initiated via API...")
		// In a real bot, we would close all positions here
		if currentPositionSize > 0 {
			log.Printf("EMERGENCY: Closing position %f for %s at %f", currentPositionSize, displaySymbol, currentPrice)
			equity += currentPrice * currentPositionSize * 0.999 // Market sell
			currentPositionSize = 0
			apiServer.SetPositions([]api.Position{})
		}
	}

	log.Println("Shutting down gracefully...")
	log.Printf("Final Equity: %f", equity)
	log.Println("Bot stopped.")
}
