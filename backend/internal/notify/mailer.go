// Package notify sends customer notifications by email. Notifications are written to an outbox table in the
// same transaction as the action they announce (see orchestrator), and a worker delivers them over SMTP.
//
// Safety: the demo dataset contains realistic-looking addresses, so when the transport is a real SMTP server
// every message is redirected to RedirectTo (required by config). Mailpit, the local default, captures mail
// without delivering it.
//
// Pipeline role: after Verify. The orchestrator queues an email only for a verified result (case opened, card
// blocked, handoff created); delivery happens later, outside the turn, so a mail outage never slows or fails a chat.
package notify

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/tls"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"mime"
	"mime/quotedprintable"
	"net"
	"net/mail"
	"net/smtp"
	"strings"
	"time"
)

// Message is one rendered email.
type Message struct {
	To      string
	Subject string
	HTML    string
	Text    string
	Inline  []Inline // images referenced from the HTML as src="cid:<CID>"
}

// Inline is an image embedded in the message, so it shows without loading remote content.
type Inline struct {
	CID         string
	Filename    string
	ContentType string
	Data        []byte
}

// Mailer delivers one rendered message. SMTPMailer is the real transport; tests use fakes.
type Mailer interface {
	Send(ctx context.Context, m Message) error
}

// SMTPMailer delivers over SMTP. Security is "ssl" (implicit TLS, port 465), "starttls" (587) or "none"
// (local catchers such as Mailpit). Credentials are optional only with "none".
type SMTPMailer struct {
	Host       string
	Port       int
	Security   string
	Username   string // SMTP login; also the envelope sender
	Password   string
	From       string // visible alias, e.g. nicebank@evon.solutions
	FromName   string
	RedirectTo string // when set, every message goes here instead of the customer's address
	Bcc        []string
	Timeout    time.Duration
}

// Send validates the recipient (after applying RedirectTo), builds the MIME message and delivers it within Timeout.
func (s *SMTPMailer) Send(ctx context.Context, m Message) error {
	to := m.To
	if s.RedirectTo != "" {
		to = s.RedirectTo
	}
	if _, err := mail.ParseAddress(to); err != nil {
		return fmt.Errorf("invalid recipient: %w", err)
	}
	raw, err := s.build(m, to)
	if err != nil {
		return err
	}
	timeout := s.Timeout
	if timeout == 0 {
		timeout = 20 * time.Second
	}
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- s.deliver(ctx, to, raw) }()
	select {
	case err := <-done:
		return err
	case <-ctx.Done():
		return fmt.Errorf("smtp: %w", ctx.Err())
	}
}

func (s *SMTPMailer) deliver(ctx context.Context, to string, raw []byte) error {
	addr := net.JoinHostPort(s.Host, fmt.Sprint(s.Port))
	dialer := &net.Dialer{Timeout: 10 * time.Second}
	tlsConf := &tls.Config{ServerName: s.Host, MinVersion: tls.VersionTLS12}

	var conn net.Conn
	var err error
	if s.Security == "ssl" {
		conn, err = (&tls.Dialer{NetDialer: dialer, Config: tlsConf}).DialContext(ctx, "tcp", addr)
	} else {
		conn, err = dialer.DialContext(ctx, "tcp", addr)
	}
	if err != nil {
		return fmt.Errorf("smtp dial: %w", err)
	}
	if deadline, ok := ctx.Deadline(); ok {
		_ = conn.SetDeadline(deadline)
	}
	c, err := smtp.NewClient(conn, s.Host)
	if err != nil {
		conn.Close()
		return fmt.Errorf("smtp hello: %w", err)
	}
	defer c.Close()
	if s.Security == "starttls" {
		if err := c.StartTLS(tlsConf); err != nil {
			return fmt.Errorf("smtp starttls: %w", err)
		}
	}
	if s.Username != "" {
		if err := c.Auth(smtp.PlainAuth("", s.Username, s.Password, s.Host)); err != nil {
			return errors.New("smtp auth failed") // never echo server text that could contain the login
		}
	}
	envelope := s.Username
	if envelope == "" {
		envelope = s.From
	}
	if err := c.Mail(envelope); err != nil {
		return fmt.Errorf("smtp mail from: %w", err)
	}
	for _, rcpt := range append([]string{to}, s.Bcc...) {
		if err := c.Rcpt(rcpt); err != nil {
			return fmt.Errorf("smtp rcpt: %w", err)
		}
	}
	w, err := c.Data()
	if err != nil {
		return fmt.Errorf("smtp data: %w", err)
	}
	if _, err := w.Write(raw); err != nil {
		return fmt.Errorf("smtp write: %w", err)
	}
	if err := w.Close(); err != nil {
		return fmt.Errorf("smtp close data: %w", err)
	}
	return c.Quit()
}

// build writes multipart/alternative (plain text + HTML, quoted-printable), wrapped in multipart/related when
// the HTML references inline images.
func (s *SMTPMailer) build(m Message, to string) ([]byte, error) {
	boundary, related := randomHex(12), randomHex(12)
	domain := "nicebank.local"
	if at := strings.LastIndex(s.From, "@"); at >= 0 {
		domain = s.From[at+1:]
	}
	var b bytes.Buffer
	from := (&mail.Address{Name: s.FromName, Address: s.From}).String()
	headers := [][2]string{
		{"From", from},
		{"Reply-To", s.From},
		{"To", to},
		{"Subject", mime.QEncoding.Encode("utf-8", m.Subject)},
		{"Date", time.Now().Format(time.RFC1123Z)},
		{"Message-ID", fmt.Sprintf("<%s@%s>", randomHex(16), domain)},
		{"MIME-Version", "1.0"},
	}
	for _, h := range headers {
		fmt.Fprintf(&b, "%s: %s\r\n", h[0], h[1])
	}
	if len(m.Inline) > 0 {
		fmt.Fprintf(&b, "Content-Type: multipart/related; boundary=\"%s\"\r\n\r\n--%s\r\n", related, related)
	}
	fmt.Fprintf(&b, "Content-Type: multipart/alternative; boundary=\"%s\"\r\n\r\n", boundary)
	for _, part := range []struct{ ctype, body string }{{"text/plain", m.Text}, {"text/html", m.HTML}} {
		fmt.Fprintf(&b, "--%s\r\nContent-Type: %s; charset=UTF-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n", boundary, part.ctype)
		qp := quotedprintable.NewWriter(&b)
		if _, err := qp.Write([]byte(part.body)); err != nil {
			return nil, err
		}
		if err := qp.Close(); err != nil {
			return nil, err
		}
		b.WriteString("\r\n")
	}
	fmt.Fprintf(&b, "--%s--\r\n", boundary)
	if len(m.Inline) > 0 {
		for _, img := range m.Inline {
			fmt.Fprintf(&b, "\r\n--%s\r\nContent-Type: %s\r\nContent-Transfer-Encoding: base64\r\n"+
				"Content-ID: <%s>\r\nContent-Disposition: inline; filename=\"%s\"\r\n\r\n",
				related, img.ContentType, img.CID, img.Filename)
			enc := base64.StdEncoding.EncodeToString(img.Data)
			for len(enc) > 76 {
				b.WriteString(enc[:76] + "\r\n")
				enc = enc[76:]
			}
			b.WriteString(enc + "\r\n")
		}
		fmt.Fprintf(&b, "--%s--\r\n", related)
	}
	return b.Bytes(), nil
}

func randomHex(n int) string {
	buf := make([]byte, n)
	_, _ = rand.Read(buf)
	return hex.EncodeToString(buf)
}
