package pii

import (
	"encoding/base64"
	"strings"
	"testing"
)

var testKey = base64.StdEncoding.EncodeToString([]byte(strings.Repeat("k", 32)))

func TestRoundTripAndBinding(t *testing.T) {
	c, err := New(testKey, 1)
	if err != nil {
		t.Fatal(err)
	}
	blob := c.Encrypt("CUS-1", "first_name", "Rosa")
	if got, err := c.Decrypt("CUS-1", "first_name", 1, blob); err != nil || got != "Rosa" {
		t.Fatalf("round trip: %q %v", got, err)
	}
	// The same ciphertext must not decrypt for another customer, another column or another key version.
	for _, bad := range []struct {
		customer, column string
		version          int
	}{{"CUS-2", "first_name", 1}, {"CUS-1", "last_name", 1}, {"CUS-1", "first_name", 2}} {
		if _, err := c.Decrypt(bad.customer, bad.column, bad.version, blob); err == nil {
			t.Errorf("decrypted with %+v", bad)
		}
	}
	blob[len(blob)-1] ^= 1
	if _, err := c.Decrypt("CUS-1", "first_name", 1, blob); err == nil {
		t.Error("tampered ciphertext decrypted")
	}
}

func TestRejectsBadKey(t *testing.T) {
	if _, err := New("c2hvcnQ=", 1); err == nil {
		t.Fatal("short key accepted")
	}
}
