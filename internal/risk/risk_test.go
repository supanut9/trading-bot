package risk

import (
	"testing"
)

func TestAdvancedRiskManager_ValidateOrder(t *testing.T) {
	rm := NewAdvancedRiskManager(1.0, 0.01, 0.05) // Max 1.0, Risk 1%, 5% daily limit
	equity := 100000.0

	// 1. Standard BUY order
	size, ok := rm.ValidateOrder("BTCUSDT", "BUY", 50000.0, 0.1, equity, 0.02)
	if !ok {
		t.Errorf("Expected order to be valid")
	}
	if size != 0.1 {
		t.Errorf("Expected size 0.1, got %f", size)
	}

	// 2. Order exceeding max position
	size, ok = rm.ValidateOrder("BTCUSDT", "BUY", 50000.0, 2.0, equity, 0.02)
	if !ok {
		t.Errorf("Expected order to be adjusted, not rejected")
	}
	if size > 1.0 {
		t.Errorf("Expected size to be capped at 1.0, got %f", size)
	}

	// 3. Daily loss limit hit (mocking)
	rm.CheckCircuitBreaker(100000.0, 100000.0) // Set initial ATH/start of day
	rm.CheckCircuitBreaker(94000.0, 100000.0)  // 6% loss
	_, ok = rm.ValidateOrder("BTCUSDT", "BUY", 50000.0, 0.1, 94000.0, 0.02)
	if ok {
		t.Errorf("Expected order to be rejected due to circuit breaker")
	}
}

func TestAdvancedRiskManager_CheckCircuitBreaker(t *testing.T) {
	rm := NewAdvancedRiskManager(1.0, 0.01, 0.05)
	
	// Initial state
	rm.CheckCircuitBreaker(100000.0, 100000.0)
	if rm.GetSettings().IsHalted == true {
		t.Errorf("Expected system to be active")
	}

	// Small loss (within limit)
	rm.CheckCircuitBreaker(96000.0, 100000.0) // 4% loss
	if rm.GetSettings().IsHalted == true {
		t.Errorf("Expected system to be active at 4%% loss")
	}

	// Large loss (over limit)
	rm.CheckCircuitBreaker(94000.0, 100000.0) // 6% loss
	if rm.GetSettings().IsHalted == false {
		t.Errorf("Expected system to be inactive at 6%% loss")
	}
}
