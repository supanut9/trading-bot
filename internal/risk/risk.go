package risk

import (
	"log"
)

type RiskManager interface {
	ValidateOrder(symbol string, side string, price float64, size float64) (float64, bool)
}

type SimpleRiskManager struct {
	MaxPositionSize float64 // in base currency
	MaxDrawdown     float64
}

func NewSimpleRiskManager(maxSize float64) *SimpleRiskManager {
	return &SimpleRiskManager{
		MaxPositionSize: maxSize,
	}
}

func (r *SimpleRiskManager) ValidateOrder(symbol string, side string, price float64, size float64) (float64, bool) {
	// Simple rule: cap size at MaxPositionSize
	finalSize := size
	if size > r.MaxPositionSize {
		log.Printf("Risk Warning: Reducing order size from %f to %f for %s", size, r.MaxPositionSize, symbol)
		finalSize = r.MaxPositionSize
	}

	if finalSize <= 0 {
		return 0, false
	}

	return finalSize, true
}
