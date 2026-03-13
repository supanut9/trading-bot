package executor

import (
	"log"
	"time"

	"github.com/supanut9/trading-bot/internal/exchange"
)

type LiveExecutor struct {
	Exchange exchange.Exchange
}

func NewLiveExecutor(ex exchange.Exchange) *LiveExecutor {
	return &LiveExecutor{
		Exchange: ex,
	}
}

func (l *LiveExecutor) Execute(order Order) (*Fill, error) {
	log.Printf("[LiveExecutor] Dispatching %s %f %s to Exchange", order.Side, order.Size, order.Symbol)

	price, fee, err := l.Exchange.PlaceOrder(order.Symbol, order.Side, order.Type, order.Size, order.Price)
	if err != nil {
		return nil, err
	}

	return &Fill{
		Symbol:    order.Symbol,
		Side:      order.Side,
		Size:      order.Size,
		Price:     price,
		Fee:       fee,
		Timestamp: time.Now(),
	}, nil
}
