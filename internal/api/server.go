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
	router    *gin.Engine
	clients   map[*websocket.Conn]bool
	mu        sync.Mutex
	positions []Position
	PanicCh   chan bool
}

func NewAPIServer() *APIServer {
	gin.SetMode(gin.ReleaseMode)
	s := &APIServer{
		router:    gin.Default(),
		clients:   make(map[*websocket.Conn]bool),
		positions: []Position{},
		PanicCh:   make(chan bool, 1),
	}

	s.setupRoutes()
	return s
}

func (s *APIServer) setupRoutes() {
	v1 := s.router.Group("/api/v1")
	{
		v1.GET("/positions", s.handlePositions)
		v1.POST("/panic", s.handlePanic)
		v1.GET("/ws/metrics", s.handleWebSocket)
	}
}

func (s *APIServer) handlePositions(c *gin.Context) {
	s.mu.Lock()
	defer s.mu.Unlock()
	c.JSON(http.StatusOK, s.positions)
}

func (s *APIServer) SetPositions(positions []Position) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.positions = positions
}

func (s *APIServer) handlePanic(c *gin.Context) {
	log.Println("PANIC BUTTON PRESSED!")
	s.PanicCh <- true
	c.JSON(http.StatusOK, gin.H{"status": "panic_initiated"})
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
