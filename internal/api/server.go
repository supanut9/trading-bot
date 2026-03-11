package api

import (
	"log"
	"net/http"
	"sync"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins for the dashboard
	},
}

type Position struct {
	Symbol string  `json:"symbol"`
	Side   string  `json:"side"`
	Size   float64 `json:"size"`
	Entry  float64 `json:"entry"`
}

type APIServer struct {
	router  *gin.Engine
	clients map[*websocket.Conn]bool
	mu      sync.Mutex
}

func NewAPIServer() *APIServer {
	gin.SetMode(gin.ReleaseMode)
	s := &APIServer{
		router:  gin.Default(),
		clients: make(map[*websocket.Conn]bool),
	}

	s.setupRoutes()
	return s
}

func (s *APIServer) setupRoutes() {
	v1 := s.router.Group("/api/v1")
	{
		v1.GET("/positions", s.handlePositions)
		v1.GET("/ws/metrics", s.handleWebSocket)
	}
}

func (s *APIServer) handlePositions(c *gin.Context) {
	// Mock positions
	positions := []Position{
		{Symbol: "BTC/USDT", Side: "BUY", Size: 0.1, Entry: 68500.0},
	}
	c.JSON(http.StatusOK, positions)
}

func (s *APIServer) handleWebSocket(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("Failed to upgrade to websocket: %v", err)
		return
	}

	s.mu.Lock()
	s.clients[conn] = true
	s.mu.Unlock()

	defer func() {
		s.mu.Lock()
		delete(s.clients, conn)
		s.mu.Unlock()
		conn.Close()
	}()

	// Keep connection alive
	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}
}

func (s *APIServer) BroadcastMetric(metric interface{}) {
	s.mu.Lock()
	defer s.mu.Unlock()

	for client := range s.clients {
		err := client.WriteJSON(metric)
		if err != nil {
			log.Printf("Websocket error: %v", err)
			client.Close()
			delete(s.clients, client)
		}
	}
}

func (s *APIServer) Run(addr string) error {
	log.Printf("API Server listening on %s", addr)
	return s.router.Run(addr)
}
