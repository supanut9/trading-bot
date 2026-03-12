package strategy

import (
	"context"
	"log"
	"time"

	pb "github.com/supanut9/trading-bot/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type Client struct {
	conn   *grpc.ClientConn
	client pb.StrategyServiceClient
}

func NewClient(addr string) (*Client, error) {
	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, err
	}

	c := pb.NewStrategyServiceClient(conn)
	return &Client{conn: conn, client: c}, nil
}

func (c *Client) Close() {
	if c.conn != nil {
		c.conn.Close()
	}
}

func (c *Client) GetSignal(symbol string, price, open, high, low, close, volume float64) (*pb.SignalResponse, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()

	req := &pb.CandleRequest{
		Symbol:    symbol,
		Timestamp: time.Now().Format(time.RFC3339),
		Open:      open,
		High:      high,
		Low:       low,
		Close:     close,
		Volume:    volume,
		Timeframe: "1m", // Default for now
	}

	resp, err := c.client.GetSignal(ctx, req)
	if err != nil {
		log.Printf("Error calling GetSignal: %v", err)
		return nil, err
	}

	return resp, nil
}
