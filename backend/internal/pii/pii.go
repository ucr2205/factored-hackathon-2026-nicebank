// Package pii decrypts customer identity fields. Values are AES-256-GCM (nonce || ciphertext || tag) with
// associated data "<customer_id>|<column>|v<key_version>", written by the loader (etl/seed_demo.py). Binding
// the row and column means a ciphertext copied to another customer or column fails authentication.
//
// Pipeline role: Understand (names are decrypted in memory to mask them before text reaches any model),
// notifications (the worker decrypts the email address) and the audited identity reveal for the agent who
// claimed a handoff. Plaintext names never reach logs, traces, the model or the handoff payload.
package pii

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
)

// Cipher holds the AES-256-GCM key for one key version.
type Cipher struct {
	aead    cipher.AEAD
	version int
}

// New takes the base64 32-byte key (PII_KEY) and the key version it corresponds to.
func New(b64Key string, version int) (*Cipher, error) {
	key, err := base64.StdEncoding.DecodeString(b64Key)
	if err != nil || len(key) != 32 {
		return nil, errors.New("PII_KEY must be 32 bytes, base64-encoded")
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	return &Cipher{aead: aead, version: version}, nil
}

// aad is the associated data that binds a ciphertext to its row, column and key version.
func aad(customerID, column string, version int) []byte {
	return fmt.Appendf(nil, "%s|%s|v%d", customerID, column, version)
}

// ErrDecrypt hides why decryption failed (wrong key, tampering, wrong row): callers only need to know it did.
var ErrDecrypt = errors.New("pii: cannot decrypt")

// Decrypt opens a value written for customerID and column with the given key version.
func (c *Cipher) Decrypt(customerID, column string, version int, blob []byte) (string, error) {
	if version != c.version {
		return "", fmt.Errorf("pii: no key for version %d", version)
	}
	n := c.aead.NonceSize()
	if len(blob) < n+c.aead.Overhead() {
		return "", ErrDecrypt
	}
	out, err := c.aead.Open(nil, blob[:n], blob[n:], aad(customerID, column, version))
	if err != nil {
		return "", ErrDecrypt
	}
	return string(out), nil
}

// Encrypt mirrors the loader; the backend itself only decrypts, it is here for tests and future writers.
func (c *Cipher) Encrypt(customerID, column, plaintext string) []byte {
	nonce := make([]byte, c.aead.NonceSize())
	_, _ = rand.Read(nonce)
	return c.aead.Seal(nonce, nonce, []byte(plaintext), aad(customerID, column, c.version))
}
