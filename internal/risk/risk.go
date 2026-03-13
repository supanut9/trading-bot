package risk

import (
	"log"
	"time"
)

type RiskSettings struct {
	MaxPositionSize float64 `json:"max_position_size"`
	MaxRiskPerTrade float64 `json:"max_risk_per_trade"`
	DailyLossLimit  float64 `json:"daily_loss_limit"`
	MaxDrawdown     float64 `json:"max_drawdown"`
	IsHalted        bool    `json:"is_halted"`
}

type RiskManager interface {
	// ValidateOrder checks if an order is allowed and returns the adjusted size
	ValidateOrder(symbol string, side string, currentPrice float64, requestedSize float64, currentEquity float64, stopLossPct float64) (float64, bool)
	// CheckCircuitBreaker returns true if trading should be halted
	CheckCircuitBreaker(currentEquity float64, initialEquity float64) bool
	// GetSettings returns current risk configuration
	GetSettings() RiskSettings
	// UpdateSettings updates the risk configuration
	UpdateSettings(settings RiskSettings)
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

func (r *AdvancedRiskManager) GetSettings() RiskSettings {
	return RiskSettings{
		MaxPositionSize: r.MaxPositionSize,
		MaxRiskPerTrade: r.MaxRiskPerTrade,
		DailyLossLimit:  r.DailyLossLimit,
		MaxDrawdown:     r.MaxDrawdown,
		IsHalted:        r.isHalted,
	}
}

func (r *AdvancedRiskManager) UpdateSettings(settings RiskSettings) {
	r.MaxPositionSize = settings.MaxPositionSize
	r.MaxRiskPerTrade = settings.MaxRiskPerTrade
	r.DailyLossLimit = settings.DailyLossLimit
	r.MaxDrawdown = settings.MaxDrawdown
	r.isHalted = settings.IsHalted
	log.Printf("Risk Manager: Settings updated from API")
}

func (r *AdvancedRiskManager) ValidateOrder(symbol string, side string, price float64, requestedSize float64, equity float64, stopLossPct float64) (float64, bool) {
	if r.isHalted {
		log.Printf("Risk Manager: Trading is HALTED due to risk limits")
		return 0, false
	}

	// 1. Calculate Max Position Value allowed based on Risk
	// Risk = PositionValue * StopLossPct
	// MaxRisk = Equity * MaxRiskPerTrade
	// PositionValue * StopLossPct <= Equity * MaxRiskPerTrade
	// PositionValue <= (Equity * MaxRiskPerTrade) / StopLossPct

	maxRiskValue := equity * r.MaxRiskPerTrade
	maxPositionValue := maxRiskValue / stopLossPct

	// 2. Cap by Absolute Max Position Size (in Asset units)
	maxSizeByRisk := maxPositionValue / price

	finalSize := requestedSize
	if finalSize > maxSizeByRisk {
		log.Printf("Risk Manager: Reduced size %.4f -> %.4f (Risk Limit: Risking $%.2f)", finalSize, maxSizeByRisk, maxRiskValue)
		finalSize = maxSizeByRisk
	}

	if finalSize > r.MaxPositionSize {
		log.Printf("Risk Manager: Reduced size %.4f -> %.4f (Max Position Cap)", finalSize, r.MaxPositionSize)
		finalSize = r.MaxPositionSize
	}

	// 3. Ensure we have enough Equity (with a buffer)
	// We can't buy more than we have cash for.
	if side == "BUY" {
		cost := finalSize * price
		if cost > (equity * 0.98) { // Keep 2% buffer for fees/slippage
			newSize := (equity * 0.98) / price
			log.Printf("Risk Manager: Reduced size %.4f -> %.4f (Insufficient Equity)", finalSize, newSize)
			finalSize = newSize
		}
	}

	if finalSize <= 0.0001 { // Minimum viable size
		log.Printf("Risk Manager: Size %.4f too small, rejecting order", finalSize)
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
