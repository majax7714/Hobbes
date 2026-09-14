package sink

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"net"
	"sync"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// Client is one connection to a sink, held open for a session's life as
// its flight stream. Safe for concurrent use: a call's request and its
// reply are made atomic by a mutex around the round trip, since the wire
// carries exactly one reply per request line, in order.
type Client struct {
	mu   sync.Mutex
	conn net.Conn
	r    *bufio.Reader
}

// Dial connects to addr and claims its flight stream. A refusal — the
// stream is already taken — comes back as the error, and the connection
// is closed; it is never returned to the caller half-open.
func Dial(addr string) (*Client, error) {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("sink: dial %s: %w", addr, err)
	}
	c := &Client{conn: conn, r: bufio.NewReader(conn)}
	if _, err := c.call(request{Kind: "open"}); err != nil {
		conn.Close()
		return nil, err
	}
	return c, nil
}

// call sends req and reads the matching reply. A dropped connection
// surfaces as an error here, on the call that notices it — never a hang,
// since a read or write on a closed socket returns promptly.
func (c *Client) call(req request) (*response, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	b, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("sink: %w", err)
	}
	if _, err := c.conn.Write(append(b, '\n')); err != nil {
		return nil, fmt.Errorf("sink: %w", err)
	}
	line, err := c.r.ReadBytes('\n')
	if err != nil {
		return nil, fmt.Errorf("sink: %w", err)
	}
	var resp response
	if err := json.Unmarshal(bytes.TrimSpace(line), &resp); err != nil {
		return nil, fmt.Errorf("sink: malformed reply: %w", err)
	}
	if !resp.OK {
		return nil, fmt.Errorf("sink: %s", resp.Error)
	}
	return &resp, nil
}

// Record sends one flight event; the sink stamps it with its own session
// and role.
func (c *Client) Record(ev recorder.Event) error {
	_, err := c.call(request{Kind: "event", Event: &ev})
	return err
}

// Park creates rec as a pending escalation record under the sink's dir.
func (c *Client) Park(rec *escalation.Record) error {
	_, err := c.call(request{Kind: "park", Record: rec})
	return err
}

// Poll returns the escalation record id's current state.
func (c *Client) Poll(id string) (*escalation.Record, error) {
	resp, err := c.call(request{Kind: "poll", ID: id})
	if err != nil {
		return nil, err
	}
	return resp.Record, nil
}

// Expire marks the pending escalation record id as expired.
func (c *Client) Expire(id string) (*escalation.Record, error) {
	resp, err := c.call(request{Kind: "expire", ID: id})
	if err != nil {
		return nil, err
	}
	return resp.Record, nil
}

// Mail appends line to the sink's mail.jsonl and returns its sequence
// number.
func (c *Client) Mail(line MailLine) (int, error) {
	resp, err := c.call(request{Kind: "mail", Line: &line})
	if err != nil {
		return 0, err
	}
	return resp.Seq, nil
}

// Close closes the underlying connection, ending the flight stream: the
// sink writes stream_closed when it notices.
func (c *Client) Close() error {
	return c.conn.Close()
}

// SendEdit opens one connection to addr, sends a single edit request
// naming ev's tool and path, and closes — the progress hook's shape: one
// connection, one edit, one reply (ADR-107, carried into ADR-112).
func SendEdit(addr string, ev recorder.Event) error {
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return fmt.Errorf("sink: dial %s: %w", addr, err)
	}
	defer conn.Close()
	b, err := json.Marshal(request{Kind: "edit", Event: &ev})
	if err != nil {
		return fmt.Errorf("sink: %w", err)
	}
	if _, err := conn.Write(append(b, '\n')); err != nil {
		return fmt.Errorf("sink: %w", err)
	}
	line, err := bufio.NewReader(conn).ReadBytes('\n')
	if err != nil {
		return fmt.Errorf("sink: %w", err)
	}
	var resp response
	if err := json.Unmarshal(bytes.TrimSpace(line), &resp); err != nil {
		return fmt.Errorf("sink: malformed reply: %w", err)
	}
	if !resp.OK {
		return fmt.Errorf("sink: %s", resp.Error)
	}
	return nil
}
