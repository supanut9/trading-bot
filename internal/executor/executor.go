package executor

import (
	"time"
)

// Order represents an order to be executed
type Order struct {
	Symbol string
	Side   string // "BUY", "SELL"
	Type   string // "MARKET", "LIMIT"
	Size   float64
	Price  float64
}

// Fill represents a completed order execution
type Fill struct {
	Symbol    string
	Side      string
	Size      float64
	Price     float64
	Fee       float64
	Timestamp time.Time
}

// Executor interface defines how to place orders on an exchange
type Executor interface {
	Execute(order Order) (*Fill, error)
}
