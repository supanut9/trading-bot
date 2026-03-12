package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/supanut9/trading-bot/internal/api"
	"github.com/supanut9/trading-bot/internal/db"
	"github.com/supanut9/trading-bot/internal/exchange"
	"github.com/supanut9/trading-bot/internal/executor"
	"github.com/supanut9/trading-bot/internal/risk"
	"github.com/supanut9/trading-bot/internal/strategy"
)

func main() {
	log.Println("Starting Trading Bot with Binance Data (Paper Mode)...")

	symbol := "BTCUSDT" // Binance format
	displaySymbol := "BTC/USDT"
	trailingStopPct := 0.02 // 2% trailing stop

	// 1. Initialize DB
	store, err := db.NewStore("bot.db")
	if err != nil {
		log.Fatalf("Failed to initialize DB: %v", err)
	}
	defer store.Close()

	// 2. Initialize API Server
	apiServer := api.NewAPIServer(store)
	go func() {
		if err := apiServer.Run(":8081"); err != nil {
			log.Fatalf("API Server failed: %v", err)
		}
	}()

	// 3. Initialize Strategy Client
	stratClient, err := strategy.NewClient("localhost:50051")
	if err != nil {
		log.Fatalf("Failed to connect to Strategy Service: %v", err)
	}
	defer stratClient.Close()
	log.Println("Connected to Strategy Service")

	// 4. Initialize Exchange, Risk & Executor
	ex := exchange.NewBinance()
	defer ex.Close()

	rm := risk.NewAdvancedRiskManager(0.1, 0.01, 0.02) // Max 0.1 BTC, Risk 1%, 2% daily loss limit
	exe := executor.NewPaperExecutor(0.0001) // 0.01% commission

	// 5. State Management & Recovery
	equity, err := store.GetLastEquity()
	if err != nil || equity == 0 {
		equity = 100000.0 // Initial capital
		store.SaveEquity(equity)
	}
	log.Printf("Recovered Equity: %f", equity)

	currentPrice := 0.0
	currentPositionSize := 0.0
	entryPrice := 0.0
	highWaterMark := 0.0

	savedPositions, err := store.GetPositions()
	if err == nil {
		if pos, ok := savedPositions[displaySymbol]; ok {
			currentPositionSize = pos.Size
			entryPrice = pos.Entry
			highWaterMark = pos.HWM
			log.Printf("Recovered Position: %f %s at %f (HWM: %f)", currentPositionSize, displaySymbol, entryPrice, highWaterMark)
			
			// Sync with dashboard
			apiServer.SetPositions([]api.Position{
				{Symbol: displaySymbol, Side: "BUY", Size: currentPositionSize, Entry: entryPrice},
			})
		}
	}

	// 6. Data Streams & Strategy Execution
	candleCh, err := ex.WatchCandles(symbol, "1m")
	if err != nil {
		log.Fatalf("Failed to watch candles: %v", err)
	}

	tickerCh, err := ex.WatchTicker(symbol)
	if err != nil {
		log.Fatalf("Failed to watch ticker: %v", err)
	}

	// Handle Ticker (for dashboard, current price & trailing stop)
	go func() {
		for t := range tickerCh {
			currentPrice = t.Price
			
			// 1. Trailing Stop Loss Logic
			if currentPositionSize > 0 {
				// Update High Water Mark
				if currentPrice > highWaterMark {
					highWaterMark = currentPrice
					store.SavePosition(displaySymbol, "BUY", currentPositionSize, entryPrice, highWaterMark)
				}

				// Check Trigger
				stopPrice := highWaterMark * (1 - trailingStopPct)
				if currentPrice <= stopPrice {
					log.Printf("TRAILING STOP TRIGGERED: %f <= %f", currentPrice, stopPrice)
					
					fill, _ := exe.Execute(executor.Order{
						Symbol: symbol,
						Side:   "SELL",
						Type:   "MARKET",
						Size:   currentPositionSize,
						Price:  currentPrice,
					})

					equity += (fill.Price * fill.Size) - fill.Fee
					currentPositionSize = 0
					highWaterMark = 0
					
					store.SaveEquity(equity)
					store.SaveTrade(displaySymbol, "SELL", fill.Price, fill.Size)
					store.SavePosition(displaySymbol, "BUY", 0, 0, 0)
					
					apiServer.SetPositions([]api.Position{})
				}
			}

			// 2. Periodic Circuit Breaker Check
			rm.CheckCircuitBreaker(equity, 100000.0)

			// 3. Broadcast to dashboard
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
				c.Close,
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
				
				finalSize, ok := rm.ValidateOrder(symbol, resp.Side, c.Close, resp.Size, equity)
				if !ok {
					continue
				}

				// Execute Order
				fill, err := exe.Execute(executor.Order{
					Symbol: symbol,
					Side:   resp.Side,
					Type:   "MARKET",
					Size:   finalSize,
					Price:  c.Close,
				})

				if err != nil {
					log.Printf("Execution Error: %v", err)
					continue
				}

				// Handle Fill
				if fill.Side == "BUY" {
					equity -= (fill.Price * fill.Size) + fill.Fee
					currentPositionSize += fill.Size
					entryPrice = fill.Price
					if fill.Price > highWaterMark {
						highWaterMark = fill.Price
					}
				} else if fill.Side == "SELL" {
					if currentPositionSize > 0 {
						equity += (fill.Price * fill.Size) - fill.Fee
						currentPositionSize -= fill.Size
						if currentPositionSize == 0 {
							highWaterMark = 0
						}
					}
				}

				// Persist State
				store.SaveEquity(equity)
				store.SaveTrade(displaySymbol, fill.Side, fill.Price, fill.Size)
				store.SavePosition(displaySymbol, "BUY", currentPositionSize, entryPrice, highWaterMark)

				// Update dashboard
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

	// 7. Main Event Loop & Graceful Shutdown
	log.Println("Bot is running. Press Ctrl+C or use Panic Button to stop.")

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	select {
	case <-sigChan:
		log.Println("Shutdown signal received...")
	case <-apiServer.PanicCh:
		log.Println("Panic initiated via API...")
		if currentPositionSize > 0 {
			log.Printf("EMERGENCY: Closing position %f for %s at %f", currentPositionSize, displaySymbol, currentPrice)
			
			fill, _ := exe.Execute(executor.Order{
				Symbol: symbol,
				Side:   "SELL",
				Type:   "MARKET",
				Size:   currentPositionSize,
				Price:  currentPrice,
			})

			equity += (fill.Price * fill.Size) - fill.Fee
			currentPositionSize = 0
			highWaterMark = 0
			
			store.SaveEquity(equity)
			store.SaveTrade(displaySymbol, "SELL", fill.Price, fill.Size)
			store.SavePosition(displaySymbol, "BUY", 0, 0, 0)
			
			apiServer.SetPositions([]api.Position{})
		}
	}

	log.Println("Shutting down gracefully...")
	log.Printf("Final Equity: %f", equity)
	log.Println("Bot stopped.")
}
