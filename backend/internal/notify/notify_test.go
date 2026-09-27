package notify

import (
	"bufio"
	"context"
	"io"
	"mime"
	"mime/multipart"
	"net"
	"net/mail"
	"strings"
	"testing"
	"testing/fstest"
	"time"
)

var caseFacts = map[string]string{
	"case_id": "DSP-001000", "amount": "89,90 USD", "merchant": "<script>x</script>", "last4": "3407", "brand": "visa",
}

func TestRenderEscapesAndFillsFacts(t *testing.T) {
	m, err := Render(KindCaseOpened, "pt", "Lucas", "http://localhost:8088/chat", caseFacts)
	if err != nil {
		t.Fatal(err)
	}
	if m.Subject != "Abrimos sua contestação DSP-001000" {
		t.Errorf("subject = %q", m.Subject)
	}
	if strings.Contains(m.HTML, "<script>") || !strings.Contains(m.HTML, "&lt;script&gt;") {
		t.Error("merchant name must be HTML-escaped")
	}
	for _, want := range []string{"Prezado(a)", "Lucas", "DSP-001000", "89,90 USD", "Visa final 3407", "nunca pede senhas", "http://localhost:8088/chat"} {
		if !strings.Contains(m.HTML, want) || !strings.Contains(m.Text, want) {
			t.Errorf("missing %q", want)
		}
	}
	if strings.Contains(m.HTML, "Fecha") {
		t.Error("empty details must be skipped")
	}
}

// Every email follows the conversation language: no Spanish in Portuguese emails and vice versa.
func TestRenderKeepsOneLanguage(t *testing.T) {
	spanish := []string{"Estimado/a", "Tarjeta", "terminada en", "Seguridad:", "Gracias por", "Ver mi caso", "Correo automático"}
	portuguese := []string{"Prezado(a)", "Cartão", "final 3407", "Segurança:", "Obrigado", "Ver meu caso", "E-mail automático"}
	facts := map[string]string{"case_id": "DSP-1", "block_id": "BLK-1", "reference": "ABC", "last4": "3407", "brand": "visa",
		"merchant": "Tienda", "amount": "10,00 USD", "date": "1 de junio", "type": "Cargo"}
	for _, kind := range []string{KindCaseOpened, KindCardBlocked, KindHandoffCreated} {
		for lang, forbidden := range map[string][]string{"es": portuguese, "pt": spanish} {
			m, err := Render(kind, lang, "Ana", "http://app.test", facts)
			if err != nil {
				t.Fatal(err)
			}
			for _, word := range forbidden {
				if strings.Contains(m.HTML, word) || strings.Contains(m.Text, word) || strings.Contains(m.Subject, word) {
					t.Errorf("%s/%s contains %q from the other language", kind, lang, word)
				}
			}
		}
	}
}

func TestRenderFallsBackToSpanish(t *testing.T) {
	m, err := Render(KindCardBlocked, "fr", "", "", map[string]string{"last4": "7616"})
	if err != nil || m.Subject != "Bloqueamos tu tarjeta terminada en 7616" {
		t.Fatalf("subject = %q err = %v", m.Subject, err)
	}
	if !strings.Contains(m.HTML, ">terminada en 7616<") {
		t.Error("unknown brand must show the plain card text")
	}
}

func TestBrandLogoIsInlinedWhenAvailable(t *testing.T) {
	m, _ := Render(KindCardBlocked, "es", "Ana", "", map[string]string{"last4": "7616", "brand": "visa", "block_id": "BLK-1"})
	if strings.Contains(m.HTML, "cid:brand-") || !strings.Contains(m.HTML, "Visa terminada en 7616") {
		t.Fatal("without a logo file the brand name is shown as text only")
	}
	if len(m.Inline) != 1 || m.Inline[0].CID != "nicebank-mark@nicebank" || !strings.Contains(m.HTML, `src="cid:nicebank-mark@nicebank"`) {
		t.Fatalf("the NiceBank mark must be embedded in the header: %+v", m.Inline)
	}

	saved := assetFS
	defer func() { assetFS = saved }()
	assetFS = fstest.MapFS{"assets/visa.png": {Data: []byte("\x89PNG fake")}}
	m, _ = Render(KindCardBlocked, "es", "Ana", "", map[string]string{"last4": "7616", "brand": "visa", "block_id": "BLK-1"})
	if len(m.Inline) != 1 || m.Inline[0].ContentType != "image/png" {
		t.Fatalf("inline = %+v", m.Inline)
	}
	if !strings.Contains(m.HTML, `src="cid:`+m.Inline[0].CID+`"`) || !strings.Contains(m.HTML, `alt="Visa"`) {
		t.Error("logo must be referenced by CID with the brand as alt text")
	}
}

// fakeSMTP accepts one message without TLS or auth (like Mailpit) and returns what it received.
func fakeSMTP(t *testing.T) (port int, got chan [2]string) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	got = make(chan [2]string, 1)
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		defer ln.Close()
		r, w := bufio.NewReader(conn), conn
		say := func(s string) { io.WriteString(w, s+"\r\n") }
		say("220 fake")
		var rcpt, data string
		for {
			line, err := r.ReadString('\n')
			if err != nil {
				return
			}
			cmd := strings.ToUpper(strings.TrimSpace(line))
			switch {
			case strings.HasPrefix(cmd, "EHLO"), strings.HasPrefix(cmd, "HELO"):
				say("250 fake")
			case strings.HasPrefix(cmd, "MAIL FROM"):
				say("250 ok")
			case strings.HasPrefix(cmd, "RCPT TO"):
				rcpt += strings.TrimSpace(line[8:])
				say("250 ok")
			case cmd == "DATA":
				say("354 go")
				var b strings.Builder
				for {
					l, _ := r.ReadString('\n')
					if l == ".\r\n" {
						break
					}
					b.WriteString(l)
				}
				data = b.String()
				say("250 queued")
			case cmd == "QUIT":
				say("221 bye")
				got <- [2]string{rcpt, data}
				return
			default:
				say("250 ok")
			}
		}
	}()
	return ln.Addr().(*net.TCPAddr).Port, got
}

func TestSMTPMailerRedirectsAndBuildsMultipart(t *testing.T) {
	port, got := fakeSMTP(t)
	m := &SMTPMailer{Host: "127.0.0.1", Port: port, Security: "none", From: "nicebank@evon.solutions", FromName: "NiceBank",
		RedirectTo: "qa@example.test", Timeout: 5 * time.Second}
	msg, _ := Render(KindHandoffCreated, "es", "Rosa", "", map[string]string{"reference": "7F971052"})
	msg.To = "real.person@gmail.com"
	msg.Inline = []Inline{{CID: "brand-visa@nicebank", Filename: "visa.png", ContentType: "image/png", Data: []byte("png-bytes")}}
	if err := m.Send(context.Background(), msg); err != nil {
		t.Fatal(err)
	}
	res := <-got
	if !strings.Contains(res[0], "qa@example.test") || strings.Contains(res[0], "gmail") {
		t.Fatalf("recipient not redirected: %q", res[0])
	}
	parsed, err := mail.ReadMessage(strings.NewReader(res[1]))
	if err != nil {
		t.Fatal(err)
	}
	if from := parsed.Header.Get("From"); !strings.Contains(from, "nicebank@evon.solutions") || !strings.Contains(from, "NiceBank") {
		t.Errorf("From = %q", from)
	}
	if dec, _ := new(mime.WordDecoder).DecodeHeader(parsed.Header.Get("Subject")); dec != "Un especialista revisará tu caso" {
		t.Errorf("Subject = %q", dec)
	}

	// multipart/related -> [multipart/alternative -> text, html], image
	ctype, params, _ := mime.ParseMediaType(parsed.Header.Get("Content-Type"))
	if ctype != "multipart/related" {
		t.Fatalf("top-level type = %s", ctype)
	}
	rel := multipart.NewReader(parsed.Body, params["boundary"])
	alt, err := rel.NextPart()
	if err != nil {
		t.Fatal(err)
	}
	_, altParams, _ := mime.ParseMediaType(alt.Header.Get("Content-Type"))
	ar := multipart.NewReader(alt, altParams["boundary"])
	var types []string
	for {
		p, err := ar.NextPart()
		if err != nil {
			break
		}
		types = append(types, p.Header.Get("Content-Type"))
	}
	if len(types) != 2 || !strings.HasPrefix(types[0], "text/plain") || !strings.HasPrefix(types[1], "text/html") {
		t.Errorf("alternative parts = %v", types)
	}
	img, err := rel.NextPart()
	if err != nil || img.Header.Get("Content-ID") != "<brand-visa@nicebank>" || img.Header.Get("Content-Type") != "image/png" {
		t.Errorf("inline image part missing: %v %v", err, img)
	}
}
