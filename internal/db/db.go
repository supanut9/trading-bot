package db

import (
	"database/sql"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

type TradeRecord struct {
	ID        int       `json:"id"`
	Symbol    string    `json:"symbol"`
	Side      string    `json:"side"`
	Price     float64   `json:"price"`
	Size      float64   `json:"size"`
	Timestamp time.Time `json:"timestamp"`
}

type Store struct {
	db *sql.DB
}

func NewStore(dbPath string) (*Store, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, err
	}

	if err := db.Ping(); err != nil {
		return nil, err
	}

	s := &Store{db: db}
	if err := s.migrate(); err != nil {
		return nil, err
	}

	return s, nil
}

func (s *Store) migrate() error {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS equity_history (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			equity REAL,
			timestamp DATETIME
		)`,
		`CREATE TABLE IF NOT EXISTS trades (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			symbol TEXT,
			side TEXT,
			price REAL,
			size REAL,
			timestamp DATETIME
		)`,
		`CREATE TABLE IF NOT EXISTS positions (
			symbol TEXT PRIMARY KEY,
			side TEXT,
			size REAL,
			entry_price REAL,
			high_water_mark REAL,
			last_updated DATETIME
		)`,
	}

	for _, q := range queries {
		_, err := s.db.Exec(q)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) SaveEquity(equity float64) error {
	_, err := s.db.Exec("INSERT INTO equity_history (equity, timestamp) VALUES (?, ?)", equity, time.Now())
	return err
}

func (s *Store) GetLastEquity() (float64, error) {
	var equity float64
	err := s.db.QueryRow("SELECT equity FROM equity_history ORDER BY timestamp DESC LIMIT 1").Scan(&equity)
	if err == sql.ErrNoRows {
		return 0, nil
	}
	return equity, err
}

func (s *Store) SaveTrade(symbol, side string, price, size float64, timestamp ...time.Time) error {
	t := time.Now()
	if len(timestamp) > 0 {
		t = timestamp[0]
	}
	_, err := s.db.Exec("INSERT INTO trades (symbol, side, price, size, timestamp) VALUES (?, ?, ?, ?, ?)",
		symbol, side, price, size, t)
	return err
}

func (s *Store) SavePosition(symbol, side string, size, entryPrice, hwm float64) error {
	if size == 0 {
		_, err := s.db.Exec("DELETE FROM positions WHERE symbol = ?", symbol)
		return err
	}
	_, err := s.db.Exec(`INSERT INTO positions (symbol, side, size, entry_price, high_water_mark, last_updated) 
		VALUES (?, ?, ?, ?, ?, ?) 
		ON CONFLICT(symbol) DO UPDATE SET 
		side=excluded.side, size=excluded.size, entry_price=excluded.entry_price, 
		high_water_mark=excluded.high_water_mark, last_updated=excluded.last_updated`,
		symbol, side, size, entryPrice, hwm, time.Now())
	return err
}

func (s *Store) GetLastTrades(limit int) ([]TradeRecord, error) {
	rows, err := s.db.Query("SELECT id, symbol, side, price, size, timestamp FROM trades ORDER BY timestamp DESC LIMIT ?", limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var trades []TradeRecord
	for rows.Next() {
		var t TradeRecord
		if err := rows.Scan(&t.ID, &t.Symbol, &t.Side, &t.Price, &t.Size, &t.Timestamp); err != nil {
			return nil, err
		}
		trades = append(trades, t)
	}
	return trades, nil
}

func (s *Store) GetPositions() (map[string]struct {
	Side  string
	Size  float64
	Entry float64
	HWM   float64
}, error) {
	rows, err := s.db.Query("SELECT symbol, side, size, entry_price, high_water_mark FROM positions")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	res := make(map[string]struct {
		Side  string
		Size  float64
		Entry float64
		HWM   float64
	})
	for rows.Next() {
		var symbol, side string
		var size, entry, hwm float64
		if err := rows.Scan(&symbol, &side, &size, &entry, &hwm); err != nil {
			return nil, err
		}
		res[symbol] = struct {
			Side  string
			Size  float64
			Entry float64
			HWM   float64
		}{side, size, entry, hwm}
	}
	return res, nil
}

func (s *Store) Close() error {
	return s.db.Close()
}
