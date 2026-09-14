package sink

import (
	"bufio"
	"fmt"
	"net"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/majax7714/Hobbes/go/internal/recorder"
)

func TestSendEditLandsOneLine(t *testing.T) {
	addr, dir := startSink(t, Config{Session: "S-1", Role: "implementer"})
	if err := SendEdit(addr, recorder.Event{Tool: "NotebookEdit", Path: "nb.ipynb"}); err != nil {
		t.Fatal(err)
	}
	evs := waitForLines(t, filepath.Join(dir, "flight.jsonl"), 2)
	last := evs[len(evs)-1]
	if last.Tool != "NotebookEdit" || last.Path != "nb.ipynb" {
		t.Errorf("edit line = %+v", last)
	}
	if last.Session != "S-1" || last.Role != "implementer" {
		t.Errorf("edit line not stamped from config: %+v", last)
	}
}

func TestSendEditRefusalSurfacesAsError(t *testing.T) {
	addr, _ := startSink(t, Config{Session: "S-1", Role: "implementer"})
	if err := SendEdit(addr, recorder.Event{Tool: "Bash", Path: "x"}); err == nil {
		t.Error("an edit with a disallowed tool should error")
	}
	if err := SendEdit(addr, recorder.Event{Tool: "Edit", Path: ""}); err == nil {
		t.Error("an edit with an empty path should error")
	}
}

func TestSendEditUnreachableSinkIsAnError(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := ln.Addr().String()
	ln.Close()
	if err := SendEdit(addr, recorder.Event{Tool: "Edit", Path: "x"}); err == nil {
		t.Error("SendEdit to a closed port should error")
	}
}

func TestClientSafeForConcurrentUse(t *testing.T) {
	addr, dir := startSink(t, Config{Session: "S-1", Role: "implementer"})
	c, err := Dial(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()

	const n = 20
	var wg sync.WaitGroup
	errs := make(chan error, n)
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			errs <- c.Record(recorder.Event{Tool: "exec", Argv: []string{fmt.Sprintf("cmd-%d", i)}})
		}(i)
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			t.Errorf("concurrent Record: %v", err)
		}
	}

	evs := waitForLines(t, filepath.Join(dir, "flight.jsonl"), 2+n)
	count := 0
	for _, ev := range evs {
		if ev.Tool == "exec" {
			count++
		}
	}
	if count != n {
		t.Errorf("got %d exec events, want %d (a race corrupted a line)", count, n)
	}
}

// TestClientErrorsOnADeadConnectionNeverHangs stands in for a sink that
// vanished mid-session (a killed sidecar, a network partition): the next
// call must fail promptly, never hang the doer's proxy waiting on a
// reply that will not come. A hand-rolled server (not the real sink)
// gives precise control over when the connection dies.
func TestClientErrorsOnADeadConnectionNeverHangs(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
	accepted := make(chan net.Conn, 1)
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		r := bufio.NewReader(conn)
		if _, err := r.ReadBytes('\n'); err != nil { // the open request
			return
		}
		if _, err := conn.Write([]byte(`{"ok":true}` + "\n")); err != nil {
			return
		}
		accepted <- conn
	}()

	c, err := Dial(ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	conn := <-accepted
	conn.Close() // the sink is gone; no further reply will ever arrive

	errc := make(chan error, 1)
	go func() { errc <- c.Record(recorder.Event{Tool: "exec"}) }()
	select {
	case err := <-errc:
		if err == nil {
			t.Error("Record on a dead connection should return an error")
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Record hung instead of erroring")
	}
}
