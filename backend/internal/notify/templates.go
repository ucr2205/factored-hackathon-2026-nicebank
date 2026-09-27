package notify

import (
	"bytes"
	"embed"
	"fmt"
	"html/template"
	"io/fs"
	"strings"
)

//go:embed templates/layout.html
var templateFS embed.FS

// Card-brand logos (PNG) for the email; see assets/README.md. Missing files fall back to the brand name.
//
//go:embed assets
var embeddedAssets embed.FS

// assetFS is a variable so tests can supply logos.
var assetFS fs.FS = embeddedAssets

var layout = template.Must(template.ParseFS(templateFS, "templates/layout.html"))

// Kinds of customer notification (must match the notifications.kind CHECK constraint).
const (
	KindCaseOpened     = "case_opened"
	KindCardBlocked    = "card_blocked"
	KindHandoffCreated = "handoff_created"
)

type detail struct {
	Label, Value string
	Icon         template.URL // "cid:..." of an inline image shown before the value
	IconAlt      string
}

// Card brands as detected from the BIN at load time (products.card_brand).
var brandNames = map[string]string{"visa": "Visa", "mastercard": "Mastercard", "amex": "American Express"}

// cardText is the card row: "Visa terminada en 2457" / "Visa final 2457", or without brand if unknown.
func cardText(lang, brand, last4 string) string {
	if last4 == "" {
		return ""
	}
	ending := map[string]string{"es": "terminada en ", "pt": "final "}[lang] + last4
	if name := brandNames[brand]; name != "" {
		return name + " " + ending
	}
	return ending
}

// brandLogo returns the inline image for a brand, if its PNG is present in assets/.
func brandLogo(brand string) (Inline, bool) {
	if brandNames[brand] == "" {
		return Inline{}, false
	}
	data, err := fs.ReadFile(assetFS, "assets/"+brand+".png")
	if err != nil {
		return Inline{}, false
	}
	return Inline{CID: "brand-" + brand + "@nicebank", Filename: brand + ".png", ContentType: "image/png", Data: data}, true
}

// view is what layout.html renders. The design follows the team's viaticos emails: dark card, accent line
// and title colored by kind, facts table with an "Important" note, call-to-action button and dark footer.
type view struct {
	Lang, Subject, Preheader                      string
	Title, Subtitle, GreetingPrefix, Name, Lead   string
	Next, ImportantLabel, Security, SecurityLabel string
	Thanks, Footer, CTALabel, CTAURL              string
	LogoURL                                       template.URL // cid: of the NiceBank mark, when the asset is present
	Accent                                        template.CSS
	Details                                       []detail
}

// copyText holds the customer-facing text per kind and language. {placeholders} are filled from the payload,
// which contains verified facts only (written by the orchestrator after reading the records back).
type copyText struct {
	Subject, Title, Subtitle, Lead, Next string
	Details                              [][2]string // label, payload key; the first row is highlighted
}

var accents = map[string]template.CSS{
	KindCaseOpened:     "#E5769A", // NiceBank rose
	KindCardBlocked:    "#F5B942", // amber: a security action
	KindHandoffCreated: "#6FC3DF", // calm blue: a person will follow up
}

var texts = map[string]map[string]copyText{
	KindCaseOpened: {
		"es": {
			Subject:  "Abrimos tu disputa {case_id}",
			Title:    "Disputa registrada",
			Subtitle: "Verificamos que tu caso quedó abierto",
			Lead:     "Registramos tu disputa por un cargo de tu tarjeta. Estos son los datos que verificamos en nuestros registros:",
			Next:     "Te avisaremos por este medio y en la app cuando haya novedades. No necesitas hacer nada más por ahora.",
			Details: [][2]string{{"Número de disputa", "case_id"}, {"Motivo", "type"}, {"Comercio", "merchant"},
				{"Monto", "amount"}, {"Fecha del cargo", "date"}, {"Tarjeta", "card"}},
		},
		"pt": {
			Subject:  "Abrimos sua contestação {case_id}",
			Title:    "Contestação registrada",
			Subtitle: "Verificamos que seu caso foi aberto",
			Lead:     "Registramos sua contestação de uma cobrança no seu cartão. Estes são os dados que verificamos nos nossos registros:",
			Next:     "Avisaremos por aqui e pelo app quando houver novidades. Você não precisa fazer mais nada por enquanto.",
			Details: [][2]string{{"Número da contestação", "case_id"}, {"Motivo", "type"}, {"Estabelecimento", "merchant"},
				{"Valor", "amount"}, {"Data da cobrança", "date"}, {"Cartão", "card"}},
		},
	},
	KindCardBlocked: {
		"es": {
			Subject:  "Bloqueamos tu tarjeta terminada en {last4}",
			Title:    "Tarjeta bloqueada",
			Subtitle: "Aplicamos el bloqueo por tu seguridad",
			Lead:     "Bloqueamos tu tarjeta y verificamos que el bloqueo quedó aplicado. Nadie podrá usarla mientras revisamos tu caso.",
			Next:     "Un especialista de NiceBank ya tiene tu caso con todos los datos y te contactará. Si no reconoces este bloqueo, comunícate con nosotros por la app.",
			Details:  [][2]string{{"Referencia del bloqueo", "block_id"}, {"Tarjeta", "card"}},
		},
		"pt": {
			Subject:  "Bloqueamos seu cartão final {last4}",
			Title:    "Cartão bloqueado",
			Subtitle: "Aplicamos o bloqueio para sua segurança",
			Lead:     "Bloqueamos seu cartão e verificamos que o bloqueio foi aplicado. Ninguém poderá usá-lo enquanto analisamos seu caso.",
			Next:     "Um especialista da NiceBank já está com seu caso e todos os dados e entrará em contato. Se você não reconhece este bloqueio, fale conosco pelo app.",
			Details:  [][2]string{{"Referência do bloqueio", "block_id"}, {"Cartão", "card"}},
		},
	},
	KindHandoffCreated: {
		"es": {
			Subject:  "Un especialista revisará tu caso",
			Title:    "Caso con un especialista",
			Subtitle: "Una persona de nuestro equipo te acompañará",
			Lead:     "Tu solicitud necesita la revisión de una persona de nuestro equipo. Ya le pasamos todos los datos verificados.",
			Next:     "Te contactará pronto; no necesitas repetir la información.",
			Details:  [][2]string{{"Referencia", "reference"}},
		},
		"pt": {
			Subject:  "Um especialista vai analisar seu caso",
			Title:    "Caso com um especialista",
			Subtitle: "Uma pessoa da nossa equipe vai acompanhar você",
			Lead:     "Sua solicitação precisa da análise de uma pessoa da nossa equipe. Já repassamos todos os dados verificados.",
			Next:     "Ele entrará em contato em breve; você não precisa repetir as informações.",
			Details:  [][2]string{{"Referência", "reference"}},
		},
	},
}

var common = map[string]struct {
	GreetingPrefix, AnonGreeting, ImportantLabel, SecurityLabel, Security, Thanks, CTALabel, Footer string
}{
	"es": {"Estimado/a", "Hola", "Importante:", "Seguridad:",
		"NiceBank nunca te pedirá contraseñas, códigos de verificación ni los datos de tu tarjeta por correo. Si recibes un mensaje así, no respondas.",
		"Gracias por confiar en", "Ver mi caso en NiceBank",
		"© NiceBank · Banco ficticio del Factored AI & Data Hackathon 2026. Correo automático: no lo respondas."},
	"pt": {"Prezado(a)", "Olá", "Importante:", "Segurança:",
		"A NiceBank nunca pede senhas, códigos de verificação nem os dados do seu cartão por e-mail. Se receber uma mensagem assim, não responda.",
		"Obrigado por confiar na", "Ver meu caso na NiceBank",
		"© NiceBank · Banco fictício do Factored AI & Data Hackathon 2026. E-mail automático: não responda."},
}

// Render builds the email for a notification in the conversation's language (es or pt; anything else falls
// back to es). Values are HTML-escaped by html/template. appURL, when set, becomes the call-to-action link.
// The returned Message has no recipient: the worker sets it after decrypting the address.
func Render(kind, lang, firstName, appURL string, payload map[string]string) (Message, error) {
	byLang, ok := texts[kind]
	if !ok {
		return Message{}, fmt.Errorf("unknown notification kind %q", kind)
	}
	if _, ok := byLang[lang]; !ok {
		lang = "es"
	}
	facts := map[string]string{}
	for k, v := range payload {
		facts[k] = v
	}
	facts["card"] = cardText(lang, payload["brand"], payload["last4"])
	payload = facts
	c, cm := byLang[lang], common[lang]
	fill := func(s string) string {
		for k, v := range payload {
			s = strings.ReplaceAll(s, "{"+k+"}", v)
		}
		return s
	}
	v := view{Lang: lang, Subject: fill(c.Subject), Preheader: c.Subtitle, Title: c.Title, Subtitle: c.Subtitle,
		GreetingPrefix: cm.GreetingPrefix, Name: firstName, Lead: c.Lead, Next: c.Next, ImportantLabel: cm.ImportantLabel,
		Security: cm.Security, SecurityLabel: cm.SecurityLabel, Thanks: cm.Thanks, Footer: cm.Footer,
		Accent: accents[kind]}
	if firstName == "" {
		v.GreetingPrefix = cm.AnonGreeting
	}
	if appURL != "" {
		v.CTALabel, v.CTAURL = cm.CTALabel, appURL
	}
	var inline []Inline
	if data, err := fs.ReadFile(assetFS, "assets/nicebank-mark.png"); err == nil {
		logo := Inline{CID: "nicebank-mark@nicebank", Filename: "nicebank.png", ContentType: "image/png", Data: data}
		v.LogoURL = template.URL("cid:" + logo.CID)
		inline = append(inline, logo)
	}
	for _, d := range c.Details {
		val := payload[d[1]]
		if val == "" {
			continue
		}
		row := detail{Label: d[0], Value: val}
		if d[1] == "card" {
			if logo, ok := brandLogo(payload["brand"]); ok {
				row.Icon, row.IconAlt = template.URL("cid:"+logo.CID), brandNames[payload["brand"]]
				inline = append(inline, logo)
			}
		}
		v.Details = append(v.Details, row)
	}

	var b bytes.Buffer
	if err := layout.Execute(&b, v); err != nil {
		return Message{}, err
	}

	var t strings.Builder
	greeting := v.GreetingPrefix
	if firstName != "" {
		greeting += " " + firstName
	}
	fmt.Fprintf(&t, "%s\n%s\n\n%s,\n\n%s\n\n", strings.ToUpper(v.Title), v.Subtitle, greeting, v.Lead)
	for _, d := range v.Details {
		fmt.Fprintf(&t, "- %s: %s\n", d.Label, d.Value)
	}
	fmt.Fprintf(&t, "\n%s %s\n", v.ImportantLabel, v.Next)
	if v.CTAURL != "" {
		fmt.Fprintf(&t, "\n%s: %s\n", v.CTALabel, v.CTAURL)
	}
	fmt.Fprintf(&t, "\n%s %s\n\n%s\n", v.SecurityLabel, v.Security, v.Footer)
	return Message{Subject: v.Subject, HTML: b.String(), Text: t.String(), Inline: inline}, nil
}
