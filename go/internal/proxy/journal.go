package proxy

import (
	"path/filepath"
	"time"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/recorder"
	"github.com/majax7714/Hobbes/go/internal/sink"
)

// Journal is where a session's records go (ADR-112): the flight log, the
// escalation queue and the mail file. Two implementations: FileJournal,
// on a local session dir, and *sink.Client, one connection to the
// session's sidecar held for the proxy's life.
type Journal interface {
	// Record appends one flight-recorder event.
	Record(ev recorder.Event) error
	// Park creates rec as a pending escalation record.
	Park(rec *escalation.Record) error
	// Poll returns the escalation record id's current state.
	Poll(id string) (*escalation.Record, error)
	// Expire marks the pending escalation record id as expired.
	Expire(id string) (*escalation.Record, error)
	// Mail appends line to the mail file and returns its sequence number.
	Mail(line sink.MailLine) (int, error)
	// Close releases whatever the journal holds open.
	Close() error
}

// FileJournal is the journal on a local session dir: what the proxy did
// before ADR-112 moved the records to a sidecar. Kept for
// `--knowledge-only` (the host's own knowledge server, ADR-087), for the
// tests, and for a session that runs on a `--network` override.
type FileJournal struct {
	dir string
	rec *recorder.Recorder
}

// NewFileJournal opens (creating as needed) <dir>/flight.jsonl and
// returns a journal that parks escalations under <dir>/escalations and
// mails to <dir>/mail.jsonl.
func NewFileJournal(dir string) (*FileJournal, error) {
	rec, err := recorder.Open(filepath.Join(dir, "flight.jsonl"))
	if err != nil {
		return nil, err
	}
	return &FileJournal{dir: dir, rec: rec}, nil
}

// Record appends ev to the flight log.
func (j *FileJournal) Record(ev recorder.Event) error { return j.rec.Record(ev) }

// Park creates rec under <dir>/escalations.
func (j *FileJournal) Park(rec *escalation.Record) error {
	_, err := escalation.Create(filepath.Join(j.dir, "escalations"), rec)
	return err
}

// Poll loads the escalation record id from <dir>/escalations.
func (j *FileJournal) Poll(id string) (*escalation.Record, error) {
	return escalation.Load(j.escalationPath(id))
}

// Expire marks the escalation record id expired.
func (j *FileJournal) Expire(id string) (*escalation.Record, error) {
	return escalation.MarkExpired(j.escalationPath(id), time.Now())
}

// escalationPath is where id's queue record lives under the session dir.
func (j *FileJournal) escalationPath(id string) string {
	return filepath.Join(j.dir, "escalations", id+".json")
}

// Mail appends line to <dir>/mail.jsonl.
func (j *FileJournal) Mail(line sink.MailLine) (int, error) {
	return sink.AppendMail(filepath.Join(j.dir, "mail.jsonl"), line)
}

// Close closes the flight log.
func (j *FileJournal) Close() error { return j.rec.Close() }
