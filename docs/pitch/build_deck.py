"""Build the pitch deck (6 slides, NiceBank brand) in English and Spanish: docs/pitch/NiceBank-pitch-{EN,ES}.pptx.

Usage: python docs/pitch/build_deck.py   (needs python-pptx; export the PDFs from PowerPoint)
"""
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pathlib import Path

from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
LOGO = str(ROOT / "frontend" / "public" / "brand" / "nicebank-mark-512.png")
OUT = str(Path(__file__).resolve().parent)
FONT = "Montserrat"
C = {k: RGBColor.from_string(v) for k, v in dict(
    burg="7A1F3D", dark="4A1026", deep="2E0A18", rose="E8B4C3", blush="F8EEF1", ink="23161B",
    muted="6E5A62", bg="FAF7F8", div="EFE3E7", white="FFFFFF", green="2E7D32").items()}

def text(slide, x, y, w, h, s, size=14, bold=False, color="ink", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, line in enumerate(s.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.line_spacing = spacing
        r = p.add_run()
        r.text = line
        r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
        r.font.color.rgb = C[color]
    return tb


def box(slide, x, y, w, h, fill="white", line="div", radius=0.12, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = C[fill]
    if line:
        s.line.color.rgb = C[line]
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        # radius < 0.5 is an absolute corner in inches; 0.5 makes a pill
        s.adjustments[0] = 0.5 if radius >= 0.5 else min(0.5, 0.17 / min(w, h))  # same 0.17 in corner on every card
    return s


def bullets(slide, x, y, w, h, items, size=13, color="ink", dot="burg", gap=6):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        ppr = p._p.get_or_add_pPr()
        ppr.set("marL", str(Inches(0.24)))
        ppr.set("indent", str(-Inches(0.24)))
        r = p.add_run()
        r.text = "●	"
        r.font.name, r.font.size, r.font.color.rgb = FONT, Pt(size - 4), C[dot]
        r = p.add_run()
        r.text = it
        r.font.name, r.font.size, r.font.color.rgb = FONT, Pt(size), C[color]


def frame(prs, t, n, kicker, title):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = C["bg"]
    box(s, 0, 0, 13.333, 0.06, fill="burg", line=None, shape=MSO_SHAPE.RECTANGLE)  # like the app's top border
    s.shapes.add_picture(LOGO, Inches(11.62), Inches(0.38), height=Inches(0.42))
    text(s, 12.1, 0.43, 1.0, 0.35, "NiceBank", 12, True, "burg")
    text(s, 0.7, 0.45, 8, 0.3, kicker, 11, True, "burg")
    text(s, 0.7, 0.75, 10.5, 0.8, title, 30, True, "ink")
    text(s, 0.7, 7.02, 8, 0.3, t["footer"], 9, False, "muted")
    text(s, 12.13, 7.02, 0.5, 0.3, str(n), 9, True, "burg", PP_ALIGN.RIGHT)
    return s





T = {
 "en": dict(
  footer="Factored AI & Data Hackathon 2026",
  c_kicker="NICEBANK DISPUTE ASSISTANT",
  c_title="Card disputes solved in a minute, not in 15 days",
  c_sub="An AI assistant that finds the exact charge, explains it or opens the dispute, and hands specialists only the cases that need them.",
  c_pill="Spanish & Portuguese  ·  Mexico  ·  Colombia  ·  Argentina",
  p_kicker="THE CUSTOMER'S PAIN", p_title="\"I don't recognize this charge\": a 15-day wait",
  p_story_t="Today, for María",
  p_story=[("Day 1", "Sees a strange charge and calls the bank, worried."),
           ("Day 2–10", "Explains it again to a second person; nobody can find it."),
           ("Day 15", "Gets an answer, if her case did not miss the deadline.")],
  p_stats=[("40%", "of all complaints are card-charge disputes"), ("~15 days", "to resolve each one"),
           ("75%", "of those complaints are still open"), ("3.1 / 5", "customer satisfaction")],
  p_src="Source: organizer dataset, 27,133 dispute complaints in three years.",
  e_kicker="THE EXPERIENCE", e_title="María writes it the way she'd say it",
  e_caption="Real conversation from our demo (the product speaks Spanish and Portuguese)",
  e_chat=[("me", "No reconozco un cobro de 385,71 de hoy"),
          ("bot", "Encontré el cargo de 385,71 USD en Streaming Music del 17 de junio con tu tarjeta terminada en 2457. ¿Confirmas que abra una disputa por \"Cargo no reconocido\"?"),
          ("me", "✓ Confirmar"),
          ("bot", "Listo: abrí la disputa DSP-001048 por el cargo de 385,71 USD en Streaming Music. Verifiqué que el caso quedó registrado.")],
  e_out_t="Three outcomes, about a minute",
  e_out=[("Dispute opened and verified", "Found in her own history and confirmed before anything is done."),
         ("Explained, no dispute needed", "8% of card purchases are pending, declined or already reversed: it says so with the real movement."),
         ("A specialist with the full case", "High amounts, old charges or a stolen card go to a person, with nothing left to ask.")],
  v_kicker="VALUE FOR THE BANK", v_title="Value for the bank, proven",
  v_tiles=[("< 1 min", "from first message to a verified dispute, instead of ~15 days"),
           ("82%", "of routine disputes resolved automatically and correctly"),
           ("43% fewer", "cases sent to a specialist than a rules-only process"),
           ("0 / 120", "unsafe outcomes: when unsure, it asks")],
  v_strip="Specialists receive prioritized cases with verified facts and evidence: they decide, they don't re-ask.",
  s_kicker="HOW IT'S BUILT", s_title="How it's built, and why",
  s_flow=[("Message", "Spanish or Portuguese, as the customer says it"), ("Protect", "Mask personal data, refuse abuse"),
          ("Understand", "Classifier + LLM: acts only if both agree"), ("Decide", "Written policy: deadlines and limits"),
          ("Act or hand off", "Customer confirms; or a specialist gets the case")],
  s_dec=[("Autonomy", "Acts only after the customer confirms. Never moves money. High amounts go to a person."),
         ("Accuracy", "Two models must agree on the type: 86.7% correct on unseen cases, 0 unsafe."),
         ("Latency & cost", "About 1 s per reply, the LLM runs in parallel. US$0.0001 per conversation."),
         ("Human oversight", "Specialist console with full audit trail; identity shown only when a case is claimed."),
         ("Privacy & fairness", "The LLM only sees masked text. No decision uses country or segment.")],
  t_kicker="TRUST", t_title="Tested before it ever talks to a customer",
  t_chart="Correct outcomes on 120 cases it had never seen",
  t_cats=["First version", "Retrained", "+ refusal screen", "+ second opinion"],
  t_promises=[("Never moves money", "No refunds, no transfers. It opens a case; people decide the outcome."),
              ("Never shows someone else's data", "26 of 26 attempts refused, plus 60 of 60 in an independent test."),
              ("When unsure, it asks", "0 unsafe outcomes in 120 cases: every error was a question, not an action.")],
  n_kicker="NEXT STEP", n_title="Ready for a pilot",
  n_steps=[("1", "Shadow mode", "The assistant reads real, consented messages and proposes; specialists compare. No customer impact."),
           ("2", "Pilot", "One country and a share of customers, with daily quality and safety reports."),
           ("3", "Scale", "More countries and channels such as WhatsApp, with the same rules and audit trail.")],
  n_note="Built on the organizer's synthetic data; the pilot is where real customer language confirms these results.",
  n_close="When it is not sure, it asks. When a person is needed, the person gets everything.",
 ),
 "es": dict(
  footer="Factored AI & Data Hackathon 2026",
  c_kicker="ASISTENTE DE DISPUTAS NICEBANK",
  c_title="Disputas de tarjeta resueltas en un minuto, no en 15 días",
  c_sub="Un asistente con IA que encuentra el cobro exacto, lo explica o abre la disputa, y le deja al especialista solo los casos que lo necesitan.",
  c_pill="Español y portugués  ·  México  ·  Colombia  ·  Argentina",
  p_kicker="EL DOLOR DEL CLIENTE", p_title="\"No reconozco este cobro\": 15 días de espera",
  p_story_t="Hoy, para María",
  p_story=[("Día 1", "Ve un cobro raro y llama al banco, preocupada."),
           ("Día 2–10", "Le explica todo de nuevo a otra persona; nadie lo encuentra."),
           ("Día 15", "Recibe respuesta, si su caso no se pasó del plazo.")],
  p_stats=[("40%", "de los reclamos son disputas por cobros con tarjeta"), ("~15 días", "tarda en resolverse cada una"),
           ("75%", "de esos reclamos sigue abierto"), ("3,1 / 5", "satisfacción del cliente")],
  p_src="Fuente: datos del organizador, 27.133 reclamos por disputas en tres años.",
  e_kicker="LA EXPERIENCIA", e_title="María lo escribe como lo diría",
  e_caption="Conversación real de nuestra demo (el producto habla español y portugués)",
  e_chat=[("me", "No reconozco un cobro de 385,71 de hoy"),
          ("bot", "Encontré el cargo de 385,71 USD en Streaming Music del 17 de junio con tu tarjeta terminada en 2457. ¿Confirmas que abra una disputa por \"Cargo no reconocido\"?"),
          ("me", "✓ Confirmar"),
          ("bot", "Listo: abrí la disputa DSP-001048 por el cargo de 385,71 USD en Streaming Music. Verifiqué que el caso quedó registrado.")],
  e_out_t="Tres resultados, en un minuto",
  e_out=[("Disputa abierta y verificada", "Encontrada en su propio historial y confirmada antes de hacer nada."),
         ("Explicado, sin disputa", "El 8% de las compras con tarjeta está pendiente, rechazada o ya revertida: se lo dice con el movimiento real."),
         ("Un especialista con el caso completo", "Montos altos, cobros viejos o tarjeta robada van a una persona, sin nada que volver a preguntar.")],
  v_kicker="VALOR PARA EL BANCO", v_title="Valor para el banco, comprobado",
  v_tiles=[("< 1 min", "del primer mensaje a una disputa verificada, en vez de ~15 días"),
           ("82%", "de las disputas simples resueltas solas y bien"),
           ("43% menos", "casos al especialista que un proceso solo con reglas"),
           ("0 / 120", "resultados inseguros: si duda, pregunta")],
  v_strip="El especialista recibe casos priorizados con hechos verificados y evidencia: decide, no vuelve a preguntar.",
  s_kicker="CÓMO ESTÁ HECHO", s_title="Cómo está hecho, y por qué",
  s_flow=[("Mensaje", "En español o portugués, como lo diría el cliente"), ("Proteger", "Oculta datos personales y rechaza abusos"),
          ("Entender", "Clasificador + LLM: actúa solo si coinciden"), ("Decidir", "Política escrita: plazos y límites"),
          ("Actuar o derivar", "El cliente confirma; o un especialista recibe el caso")],
  s_dec=[("Autonomía", "Actúa solo si el cliente confirma. Nunca mueve dinero. Los montos altos van a una persona."),
         ("Precisión", "Dos modelos deben coincidir en el tipo: 86,7% de aciertos en casos nuevos, 0 inseguros."),
         ("Velocidad y costo", "Cerca de 1 s por respuesta; el LLM trabaja en paralelo. US$0,0001 por conversación."),
         ("Supervisión humana", "Consola del especialista con auditoría completa; la identidad solo se ve al tomar el caso."),
         ("Privacidad y equidad", "El LLM solo ve texto enmascarado. Ninguna decisión usa país ni segmento.")],
  t_kicker="CONFIANZA", t_title="Probado antes de hablar con un solo cliente",
  t_chart="Aciertos en 120 casos que nunca había visto",
  t_cats=["Primera versión", "Reentrenado", "+ detector de rechazo", "+ segunda opinión"],
  t_promises=[("Nunca mueve dinero", "Ni reembolsos ni transferencias. Abre el caso; las personas deciden."),
              ("Nunca muestra datos de otra persona", "26 de 26 intentos rechazados, y 60 de 60 en una prueba independiente."),
              ("Si duda, pregunta", "0 resultados inseguros en 120 casos: cada error fue una pregunta, no una acción.")],
  n_kicker="PRÓXIMO PASO", n_title="Listo para un piloto",
  n_steps=[("1", "Modo sombra", "El asistente lee mensajes reales con consentimiento y propone; los especialistas comparan. Sin impacto en clientes."),
           ("2", "Piloto", "Un país y una parte de los clientes, con reportes diarios de calidad y seguridad."),
           ("3", "Escalar", "Más países y canales como WhatsApp, con las mismas reglas y auditoría.")],
  n_note="Construido con los datos sintéticos del organizador; el piloto es donde el lenguaje real de los clientes confirma estos resultados.",
  n_close="Si no está seguro, pregunta. Si hace falta una persona, la persona recibe todo.",
 ),
}


def bubble(s, x_right, x_left, y, maxw, msg, mine):
    cpi = 8.6 if mine else 9.4                     # characters per inch at 12 pt (bold is wider)
    one_line = len(msg) / cpi + 0.45
    w = min(maxw, max(1.6, one_line))
    lines = 1 if one_line <= maxw else -(-len(msg) // int((maxw - 0.45) * cpi))
    h = 0.24 + 0.24 * lines
    x = x_right - w if mine else x_left
    box(s, x, y, w, h, fill="burg" if mine else "white", line=None if mine else "div", radius=0.5 if lines == 1 else 0.2)
    text(s, x + 0.22, y, w - 0.4, h, msg, 12, mine, "white" if mine else "ink", anchor=MSO_ANCHOR.MIDDLE)
    return h


def build(lang):
    t = T[lang]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    # 1 — Cover: the promise
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = C["deep"]
    for (x, y, d, col) in ((9.4, -1.6, 6.2, "dark"), (10.9, 3.6, 4.4, "burg")):
        box(s, x, y, d, d, fill=col, line=None, shape=MSO_SHAPE.OVAL)
    s.shapes.add_picture(LOGO, Inches(0.8), Inches(0.8), height=Inches(0.9))
    text(s, 1.85, 1.02, 4, 0.5, "NiceBank", 24, True, "white")
    text(s, 0.8, 2.15, 8, 0.35, t["c_kicker"], 12, True, "rose")
    text(s, 0.8, 2.5, 9.0, 2.3, t["c_title"], 42, True, "white", spacing=0.95)
    text(s, 0.8, 4.5, 8.2, 1.0, t["c_sub"], 16, False, "rose", spacing=1.1)
    box(s, 0.8, 6.1, 6.4, 0.5, fill="burg", line=None, radius=0.5)
    text(s, 0.8, 6.1, 6.4, 0.5, t["c_pill"], 12, True, "white", PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    text(s, 0.8, 6.9, 8, 0.3, t["footer"], 10, False, "rose")

    # 2 — The customer's pain
    s = frame(prs, t, 2, t["p_kicker"], t["p_title"])
    box(s, 0.7, 1.9, 5.6, 4.65, fill="white")
    text(s, 1.05, 2.1, 5, 0.45, t["p_story_t"], 18, True, "ink")
    for i, (when, what) in enumerate(t["p_story"]):
        y = 2.8 + i * 1.2
        box(s, 1.05, y, 0.42, 0.42, fill="burg" if i < 2 else "rose", line=None, shape=MSO_SHAPE.OVAL)
        if i < 2:
            box(s, 1.24, y + 0.42, 0.04, 0.78, fill="rose", line=None, shape=MSO_SHAPE.RECTANGLE)
        text(s, 1.7, y - 0.02, 4.3, 0.35, when, 13, True, "burg")
        text(s, 1.7, y + 0.3, 4.3, 0.8, what, 13, False, "muted")
    for i, (num, cap) in enumerate(t["p_stats"]):
        col, row = i % 2, i // 2
        x, y = 6.6 + col * 3.05, 1.9 + row * 2.3
        hero = i == 0
        box(s, x, y, 2.9, 2.1, fill="burg" if hero else "white", line=None if hero else "div")
        text(s, x + 0.25, y + 0.25, 2.5, 0.8, num, 34, True, "white" if hero else "burg")
        text(s, x + 0.25, y + 1.1, 2.45, 0.9, cap, 12.5, False, "blush" if hero else "muted")
    text(s, 6.6, 6.55, 6, 0.3, t["p_src"], 9.5, False, "muted")

    # 3 — The experience
    s = frame(prs, t, 3, t["e_kicker"], t["e_title"])
    box(s, 0.7, 1.9, 6.0, 4.95, fill="blush", line="rose")
    y = 2.15
    for who, msg in t["e_chat"]:
        mine = who == "me"
        y += bubble(s, 6.45, 0.95, y, 4.2 if mine else 4.9, msg, mine) + 0.22
    text(s, 0.95, 6.45, 5.6, 0.35, t["e_caption"], 9.5, False, "muted")
    text(s, 7.1, 1.95, 5.5, 0.45, t["e_out_t"], 18, True, "ink")
    for i, (h, b) in enumerate(t["e_out"]):
        y = 2.55 + i * 1.45
        box(s, 7.1, y, 5.55, 1.3, fill="white")
        box(s, 7.35, y + 0.3, 0.5, 0.5, fill="burg", line=None, shape=MSO_SHAPE.OVAL)
        text(s, 7.35, y + 0.3, 0.5, 0.5, "✓", 16, True, "white", PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
        text(s, 8.1, y + 0.18, 4.4, 0.4, h, 14, True, "ink")
        text(s, 8.1, y + 0.55, 4.4, 0.75, b, 11.5, False, "muted")

    # 4 — Value, proven: KPI tiles + the improvement chart
    s = frame(prs, t, 4, t["v_kicker"], t["v_title"])
    for i, (big, cap) in enumerate(t["v_tiles"]):
        col, row = i % 2, i // 2
        x, y = 0.7 + col * 3.15, 1.85 + row * 2.45
        hero = i == 0
        box(s, x, y, 3.0, 2.25, fill="burg" if hero else "white", line=None if hero else "div")
        text(s, x + 0.25, y + 0.22, 2.6, 0.8, big, 30, True, "white" if hero else "burg")
        text(s, x + 0.25, y + 1.05, 2.55, 1.1, cap, 12, False, "blush" if hero else "muted", spacing=1.05)
    box(s, 7.15, 1.85, 5.5, 4.7, fill="white")
    text(s, 7.4, 2.0, 5.0, 0.4, t["t_chart"], 13, True, "ink")
    data = CategoryChartData()
    data.categories = t["t_cats"]
    data.add_series("%", (65.0, 70.8, 79.2, 86.7))
    ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(7.3), Inches(2.5), Inches(5.2), Inches(3.95), data).chart
    ch.has_legend = False
    ch.has_title = False
    ch.font.name, ch.font.size = FONT, Pt(10)
    ch.font.color.rgb = C["muted"]
    va = ch.value_axis
    va.maximum_scale, va.minimum_scale = 100, 0
    va.visible = False
    va.has_major_gridlines = False
    ch.category_axis.format.line.color.rgb = C["div"]
    plot = ch.plots[0]
    plot.gap_width = 55
    plot.has_data_labels = True
    for idx, pt in enumerate(plot.series[0].points):
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = C["burg"] if idx == 3 else C["rose"]
        label = f"{(65.0, 70.8, 79.2, 86.7)[idx]:.1f}%"
        tf = pt.data_label.text_frame
        tf.text = label if lang == "en" else label.replace(".", ",")
        r = tf.paragraphs[0].runs[0]
        r.font.name, r.font.size, r.font.bold = FONT, Pt(12), True
        r.font.color.rgb = C["ink"]
        pt.data_label.position = XL_LABEL_POSITION.OUTSIDE_END
    text(s, 0.7, 6.65, 11.95, 0.3, t["v_strip"], 10.5, False, "muted")

    # 5 — How it's built, and why: flow + the decisions the challenge asks to justify
    s = frame(prs, t, 5, t["s_kicker"], t["s_title"])
    for i, (h, b) in enumerate(t["s_flow"]):
        x = 0.7 + i * 2.43
        dark = i in (2, 3)
        box(s, x, 1.85, 2.18, 1.55, fill="burg" if dark else "white", line=None if dark else "div")
        text(s, x + 0.18, 1.98, 1.85, 0.4, h, 14, True, "white" if dark else "ink")
        text(s, x + 0.18, 2.42, 1.85, 0.95, b, 10.5, False, "blush" if dark else "muted", spacing=1.0)
        if i < 4:
            ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 2.2), Inches(2.5), Inches(0.2), Inches(0.26))
            ar.fill.solid()
            ar.fill.fore_color.rgb = C["rose"]
            ar.line.fill.background()
    for i, (h, b) in enumerate(t["s_dec"]):
        top = i < 3
        w = 3.85 if top else 5.9
        x = 0.7 + (i * 4.05 if top else (i - 3) * 6.05)
        y = 3.7 if top else 5.25
        box(s, x, y, w, 1.38, fill="white")
        box(s, x + 0.16, y + 0.3, 0.07, 0.78, fill="burg", line=None, shape=MSO_SHAPE.RECTANGLE)
        text(s, x + 0.42, y + 0.15, w - 0.6, 0.4, h, 13.5, True, "burg")
        text(s, x + 0.42, y + 0.55, w - 0.6, 0.8, b, 11, False, "ink", spacing=1.0)

    # 6 — Pilot
    s = frame(prs, t, 6, t["n_kicker"], t["n_title"])
    for i, (num, h, b) in enumerate(t["n_steps"]):
        x = 0.7 + i * 4.05
        box(s, x, 1.95, 3.85, 2.55, fill="white")
        box(s, x + 0.3, 2.25, 0.7, 0.7, fill="burg" if i == 0 else ("dark" if i == 1 else "deep"), line=None, shape=MSO_SHAPE.OVAL)
        text(s, x + 0.3, 2.25, 0.7, 0.7, num, 20, True, "white", PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
        text(s, x + 1.2, 2.38, 2.5, 0.5, h, 19, True, "ink")
        text(s, x + 0.3, 3.2, 3.3, 1.6, b, 12.5, False, "muted", spacing=1.05)
        if i < 2:
            arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 3.88), Inches(3.27), Inches(0.14), Inches(0.3))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = C["rose"]
            arrow.line.fill.background()
    text(s, 0.7, 4.75, 11.95, 0.4, t["n_note"], 11, False, "muted")
    box(s, 0.7, 5.45, 11.95, 1.1, fill="deep", line=None)
    s.shapes.add_picture(LOGO, Inches(1.0), Inches(5.7), height=Inches(0.6))
    text(s, 1.85, 5.45, 10.5, 1.1, t["n_close"], 18, True, "white", anchor=MSO_ANCHOR.MIDDLE)

    path = str(Path(OUT) / f"NiceBank-pitch-{lang.upper()}.pptx")
    prs.save(path)
    print(path)


for lang in ("en", "es"):
    build(lang)
