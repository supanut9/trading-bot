package exchange

import (
	"time"
)

type MockExchange struct {
	stopCh chan struct{}
}

func NewMockExchange() *MockExchange {
	return &MockExchange{
		stopCh: make(chan struct{}),
	}
}

func (m *MockExchange) WatchCandles(symbol string, interval string) (<-chan Candle, error) {
	ch := make(chan Candle, 10)
	go func() {
		ticker := time.NewTicker(2 * time.Second)
		defer ticker.Stop()
		price := 70000.0
		for {
			select {
			case <-m.stopCh:
				return
			case t := <-ticker.C:
				price += float64((time.Now().Unix() % 100) - 50)
				ch <- Candle{
					Symbol: symbol,
					Time:   t,
					Open:   price - 10,
					High:   price + 20,
					Low:    price - 20,
					Close:  price + 5,
					Volume: 1000.0,
				}
			}
		}
	}()
	return ch, nil
}

func (m *MockExchange) WatchTicker(symbol string) (<-chan Ticker, error) {
	ch := make(chan Ticker, 10)
	go func() {
		ticker := time.NewTicker(1 * time.Second)
		defer ticker.Stop()
		price := 70000.0
		for {
			select {
			case <-m.stopCh:
				return
			case t := <-ticker.C:
				price += float64((time.Now().Unix() % 10) - 5)
				ch <- Ticker{
					Symbol: symbol,
					Price:  price,
					Time:   t,
				}
			}
		}
	}()
	return ch, nil
}

func (m *MockExchange) Close() error {
	close(m.stopCh)
	return nil
}
