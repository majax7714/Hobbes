// Package lib is the second module of the twomod fixture: the module
// the app module reaches through a replace directive (dagger's sdk/go
// shape, C-33). It carries one interface-dispatch call so the oracle
// harness meets the dynamic case on a hand-computable graph.
package lib

// Greet is a plain cross-module static call target.
func Greet(name string) string {
	return "hi " + name
}

// Store is the interface behind the fixture's one dynamic call.
type Store interface {
	Get(key string) string
}

// MemStore is the only implementation of Store in the fixture.
type MemStore struct{}

// Get returns the key unchanged.
func (MemStore) Get(key string) string {
	return key
}

// Lookup dispatches through the interface: the oracle resolves s.Get to
// MemStore.Get, Hobbes' semantic lane resolves it to Store.Get.
func Lookup(s Store, key string) string {
	return s.Get(key)
}
