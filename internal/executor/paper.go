package executor

import (
	"log"
	"time"
)

type PaperExecutor struct {
	CommissionRate float64
}

func NewPaperExecutor(commission float64) *PaperExecutor {
	return &PaperExecutor{
		CommissionRate: commission,
	}
}

func (p *PaperExecutor) Execute(order Order) (*Fill, error) {
	log.Printf("[PaperExecutor] Executing %s %f %s at %f", order.Side, order.Size, order.Symbol, order.Price)

	fee := order.Price * order.Size * p.CommissionRate

	return &Fill{
		Symbol:    order.Symbol,
		Side:      order.Side,
		Size:      order.Size,
		Price:     order.Price,
		Fee:       fee,
		Timestamp: time.Now(),
	}, nil
}
