package api

import (
	"log"
	"net/http"
	"sync"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/supanut9/trading-bot/internal/db"
	"github.com/supanut9/trading-bot/internal/risk"
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
	store     *db.Store
	rm        risk.RiskManager
}

func CORSMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

func NewAPIServer(store *db.Store, rm risk.RiskManager) *APIServer {
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()
	router.Use(CORSMiddleware())

	s := &APIServer{
		router:    router,
		clients:   make(map[*websocket.Conn]bool),
		positions: []Position{},
		PanicCh:   make(chan bool, 1),
		store:     store,
		rm:        rm,
	}

	s.setupRoutes()
	return s
}

func (s *APIServer) setupRoutes() {
	v1 := s.router.Group("/api/v1")
	{
		v1.GET("/positions", s.handlePositions)
		v1.GET("/trades", s.handleTrades)
		v1.POST("/panic", s.handlePanic)
		v1.GET("/ws/metrics", s.handleWebSocket)
		v1.GET("/risk", s.handleRisk)
		v1.PUT("/risk", s.handleUpdateRisk)
	}
}

func (s *APIServer) handleRisk(c *gin.Context) {
	if s.rm == nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Risk Manager not initialized"})
		return
	}
	c.JSON(http.StatusOK, s.rm.GetSettings())
}

func (s *APIServer) handleUpdateRisk(c *gin.Context) {
	if s.rm == nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Risk Manager not initialized"})
		return
	}

	var settings risk.RiskSettings
	if err := c.ShouldBindJSON(&settings); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	s.rm.UpdateSettings(settings)
	c.JSON(http.StatusOK, gin.H{"status": "updated", "settings": s.rm.GetSettings()})
}

func (s *APIServer) handlePositions(c *gin.Context) {
	s.mu.Lock()
	defer s.mu.Unlock()
	c.JSON(http.StatusOK, s.positions)
}

func (s *APIServer) handleTrades(c *gin.Context) {
	if s.store == nil {
		c.JSON(http.StatusOK, []interface{}{})
		return
	}
	trades, err := s.store.GetLastTrades(50)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, trades)
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
