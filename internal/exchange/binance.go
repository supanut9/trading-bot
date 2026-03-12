package exchange

import (
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

const (
	BinancePublicWS = "wss://stream.binance.com:9443/ws"
)

type Binance struct {
	mu          sync.RWMutex
	conns       []*websocket.Conn
	stopCh      chan struct{}
	candleChs   map[string]chan Candle
	tickerChs   map[string]chan Ticker
}

func NewBinance() *Binance {
	return &Binance{
		stopCh:    make(chan struct{}),
		candleChs: make(map[string]chan Candle),
		tickerChs: make(map[string]chan Ticker),
	}
}

// WatchCandles starts a WebSocket for Binance K-lines
func (b *Binance) WatchCandles(symbol string, interval string) (<-chan Candle, error) {
	b.mu.Lock()
	defer b.mu.Unlock()

	key := fmt.Sprintf("%s_%s", strings.ToLower(symbol), interval)
	if ch, ok := b.candleChs[key]; ok {
		return ch, nil
	}

	ch := make(chan Candle, 100)
	b.candleChs[key] = ch

	// Connect to Binance WS
	// Stream name: <symbol>@kline_<interval>
	streamName := fmt.Sprintf("%s@kline_%s", strings.ToLower(strings.ReplaceAll(symbol, "/", "")), interval)
	url := fmt.Sprintf("%s/%s", BinancePublicWS, streamName)

	go b.connectAndListen(url, "candle", key)

	return ch, nil
}

// WatchTicker starts a WebSocket for Binance individual symbol ticker
func (b *Binance) WatchTicker(symbol string) (<-chan Ticker, error) {
	b.mu.Lock()
	defer b.mu.Unlock()

	key := strings.ToLower(symbol)
	if ch, ok := b.tickerChs[key]; ok {
		return ch, nil
	}

	ch := make(chan Ticker, 100)
	b.tickerChs[key] = ch

	// Stream name: <symbol>@ticker
	streamName := fmt.Sprintf("%s@ticker", strings.ToLower(strings.ReplaceAll(symbol, "/", "")))
	url := fmt.Sprintf("%s/%s", BinancePublicWS, streamName)

	go b.connectAndListen(url, "ticker", key)

	return ch, nil
}

func (b *Binance) connectAndListen(url string, streamType string, key string) {
	var conn *websocket.Conn
	var err error

	for {
		select {
		case <-b.stopCh:
			return
		default:
			conn, _, err = websocket.DefaultDialer.Dial(url, nil)
			if err != nil {
				log.Printf("Binance WS Dial Error: %v, retrying in 5s...", err)
				time.Sleep(5 * time.Second)
				continue
			}

			b.mu.Lock()
			b.conns = append(b.conns, conn)
			b.mu.Unlock()

			log.Printf("Connected to Binance WS: %s", url)
			
			for {
				_, message, err := conn.ReadMessage()
				if err != nil {
					log.Printf("Binance WS Read Error: %v, reconnecting...", err)
					break
				}

				if streamType == "candle" {
					b.handleCandle(message, key)
				} else if streamType == "ticker" {
					b.handleTicker(message, key)
				}
			}
			
			conn.Close()
			time.Sleep(1 * time.Second)
		}
	}
}

// Binance K-line stream payload
type klinePayload struct {
	Symbol string `json:"s"`
	Data   struct {
		T int64  `json:"t"` // Start time
		O string `json:"o"` // Open
		H string `json:"h"` // High
		L string `json:"l"` // Low
		C string `json:"c"` // Close
		V string `json:"v"` // Volume
		X bool   `json:"x"` // Is this kline closed?
	} `json:"k"`
}

func (b *Binance) handleCandle(message []byte, key string) {
	var p klinePayload
	if err := json.Unmarshal(message, &p); err != nil {
		return
	}

	// We only send closed candles to strategy
	if !p.Data.X {
		return
	}

	open, _ := strconv.ParseFloat(p.Data.O, 64)
	high, _ := strconv.ParseFloat(p.Data.H, 64)
	low, _ := strconv.ParseFloat(p.Data.L, 64)
	close, _ := strconv.ParseFloat(p.Data.C, 64)
	volume, _ := strconv.ParseFloat(p.Data.V, 64)

	candle := Candle{
		Symbol: p.Symbol,
		Time:   time.Unix(p.Data.T/1000, 0),
		Open:   open,
		High:   high,
		Low:    low,
		Close:  close,
		Volume: volume,
	}

	b.mu.RLock()
	ch, ok := b.candleChs[key]
	b.mu.RUnlock()

	if ok {
		ch <- candle
	}
}

// Binance Ticker stream payload
type tickerPayload struct {
	Symbol string `json:"s"`
	Price  string `json:"c"` // Current price (last trade)
}

func (b *Binance) handleTicker(message []byte, key string) {
	var p tickerPayload
	if err := json.Unmarshal(message, &p); err != nil {
		return
	}

	price, _ := strconv.ParseFloat(p.Price, 64)

	ticker := Ticker{
		Symbol: p.Symbol,
		Price:  price,
		Time:   time.Now(),
	}

	b.mu.RLock()
	ch, ok := b.tickerChs[key]
	b.mu.RUnlock()

	if ok {
		select {
		case ch <- ticker:
		default:
			// Drop if channel is full to avoid blocking WS reader
		}
	}
}

func (b *Binance) Close() error {
	close(b.stopCh)
	b.mu.Lock()
	defer b.mu.Unlock()
	for _, conn := range b.conns {
		conn.Close()
	}
	return nil
}
