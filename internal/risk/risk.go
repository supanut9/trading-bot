package risk

import (
	"log"
	"time"
)

type RiskManager interface {
	// ValidateOrder checks if an order is allowed and returns the adjusted size
	ValidateOrder(symbol string, side string, currentPrice float64, requestedSize float64, currentEquity float64) (float64, bool)
	// CheckCircuitBreaker returns true if trading should be halted
	CheckCircuitBreaker(currentEquity float64, initialEquity float64) bool
}

type AdvancedRiskManager struct {
	MaxPositionSize float64 // Absolute max size in base currency
	MaxRiskPerTrade float64 // % of equity to risk per trade (0.01 = 1%)
	DailyLossLimit  float64 // % of equity (0.02 = 2%)
	MaxDrawdown     float64 // % from ATH (0.10 = 10%)

	athEquity        float64
	startOfDayEquity float64
	lastReset        time.Time
	isHalted         bool
}

func NewAdvancedRiskManager(maxSize float64, riskPerTrade float64, dailyLoss float64) *AdvancedRiskManager {
	return &AdvancedRiskManager{
		MaxPositionSize: maxSize,
		MaxRiskPerTrade: riskPerTrade,
		DailyLossLimit:  dailyLoss,
		MaxDrawdown:     0.10, // 10% default
		lastReset:       time.Now(),
	}
}

func (r *AdvancedRiskManager) ValidateOrder(symbol string, side string, price float64, size float64, equity float64) (float64, bool) {
	if r.isHalted {
		log.Printf("Risk Manager: Trading is HALTED due to risk limits")
		return 0, false
	}

	// 1. Calculate size based on % of equity if size is 0 or too large
	// If requested size is > MaxPositionSize, cap it
	finalSize := size
	if size > r.MaxPositionSize {
		finalSize = r.MaxPositionSize
	}

	// 2. Ensure we don't buy more than we can afford (simple check)
	if side == "BUY" && (finalSize*price) > equity {
		finalSize = (equity * 0.95) / price // Use 95% of equity max
	}

	if finalSize <= 0 {
		return 0, false
	}

	return finalSize, true
}

func (r *AdvancedRiskManager) CheckCircuitBreaker(currentEquity float64, initialEquity float64) bool {
	// Initialize ATH and Daily Start if first run
	if r.athEquity == 0 {
		r.athEquity = currentEquity
		r.startOfDayEquity = currentEquity
	}

	// Update ATH
	if currentEquity > r.athEquity {
		r.athEquity = currentEquity
	}

	// Reset daily start equity every 24h
	if time.Since(r.lastReset) > 24*time.Hour {
		r.startOfDayEquity = currentEquity
		r.lastReset = time.Now()
		r.isHalted = false // Reset halt daily
	}

	// 1. Check Max Drawdown from ATH
	drawdown := (r.athEquity - currentEquity) / r.athEquity
	if drawdown > r.MaxDrawdown {
		log.Printf("CRITICAL: Max Drawdown exceeded (%.2f%%). Halting.", drawdown*100)
		r.isHalted = true
		return true
	}

	// 2. Check Daily Loss Limit
	dailyLoss := (r.startOfDayEquity - currentEquity) / r.startOfDayEquity
	if dailyLoss > r.DailyLossLimit {
		log.Printf("WARNING: Daily Loss Limit exceeded (%.2f%%). Halting for today.", dailyLoss*100)
		r.isHalted = true
		return true
	}

	return r.isHalted
}
