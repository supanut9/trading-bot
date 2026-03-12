package exchange

import (
	"time"
)

// Candle represents an OHLCV bar
type Candle struct {
	Symbol string
	Time   time.Time
	Open   float64
	High   float64
	Low    float64
	Close  float64
	Volume float64
}

// Ticker represents current market price
type Ticker struct {
	Symbol string
	Price  float64
	Time   time.Time
}

// Exchange interface defines common methods for interacting with crypto exchanges
type Exchange interface {
	// WatchCandles returns a channel that receives real-time OHLCV data
	WatchCandles(symbol string, interval string) (<-chan Candle, error)

	// WatchTicker returns a channel that receives real-time price updates
	WatchTicker(symbol string) (<-chan Ticker, error)

	// Close closes all WebSocket connections
	Close() error
}
