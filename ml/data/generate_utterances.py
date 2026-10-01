"""Generate the team_generated training corpus for the dispute-type classifier (taxonomy C6).

The organizer dataset has no dispute text (see docs/ml_labels.md), so the corpus is written from templates:
each label has several *families* of core phrasings per language, combined with slots (amounts, dates,
merchants, card type, openers, closers) and noise (typos, missing accents, casing, PII placeholders as produced
by backend/internal/guard.Mask). Whole families are assigned to one split, so validation and test measure
phrasings the model never saw in training (the split is by template family, not random rows).

Out-of-scope also includes the balance-inquiry turns from the real transcripts (data/silver/call_transcripts):
they are masked with the same rules as the backend and never written to a committed file.

Outputs (ml/data/build/, git-ignored):
    corpus.jsonl    one row per utterance: {id, text, label, lang, split, family, source}
    manifest.json   seed, counts per split/label/lang, SHA-256 of every text and of the whole corpus

Usage: poetry run python ml/data/generate_utterances.py [--per-family 20] [--seed 20260930]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ml" / "data" / "build"
TRANSCRIPTS = ROOT / "data" / "silver" / "call_transcripts"

LABELS = ["unrecognized_charge", "duplicate_charge", "wrong_amount", "not_received",
          "atm_cash_not_dispensed", "card_lost_stolen", "other_in_scope", "out_of_scope"]

# ---------------------------------------------------------------------------------------------------------
# Core phrasings. Each inner list is one family; {amt} {date} {merchant} {card} are optional slots.
# ---------------------------------------------------------------------------------------------------------
FAMILIES: dict[str, dict[str, list[list[str]]]] = {
    "unrecognized_charge": {
        "es": [
            ["no reconozco un cargo de {amt} {date}", "no reconozco este cobro de {amt}", "hay un cargo que no reconozco en {card}"],
            ["yo no hice esa compra de {amt} en {merchant}", "no hice ninguna compra en {merchant} {date}", "esa compra no la hice yo"],
            ["no autoricé un pago de {amt} {date}", "aparece un pago que nunca autoricé", "no di autorización para ese cargo en {merchant}"],
            ["alguien usó mi {card} para comprar en {merchant}", "creo que alguien está usando mi tarjeta, hay una compra de {amt} que no es mía"],
            ["me aparece un consumo desconocido de {amt}", "tengo un consumo que no es mío {date}", "hay un movimiento desconocido en mi estado de cuenta de {amt}"],
            ["me cobraron algo que yo no compré, {amt} en {merchant}", "me llegó un cargo de {merchant} y nunca compré ahí"],
            ["quiero desconocer un cargo de {amt} {date}", "necesito desconocer una transacción en {merchant}"],
        ],
        "pt": [
            ["não reconheço uma cobrança de {amt} {date}", "não reconheço essa compra de {amt}", "tem uma cobrança que eu não reconheço no {card}"],
            ["eu não fiz essa compra de {amt} no {merchant}", "não fiz nenhuma compra no {merchant} {date}", "essa compra não fui eu que fiz"],
            ["não autorizei um pagamento de {amt} {date}", "apareceu um pagamento que eu nunca autorizei", "não autorizei essa cobrança do {merchant}"],
            ["alguém usou meu {card} para comprar no {merchant}", "acho que alguém está usando meu cartão, tem uma compra de {amt} que não é minha"],
            ["apareceu um gasto desconhecido de {amt}", "tem um lançamento que não é meu {date}", "tem uma transação desconhecida na minha fatura de {amt}"],
            ["me cobraram uma coisa que eu não comprei, {amt} no {merchant}", "veio uma cobrança do {merchant} e eu nunca comprei lá"],
            ["quero contestar uma compra que não reconheço de {amt} {date}", "preciso contestar uma transação que não fiz no {merchant}"],
        ],
    },
    "duplicate_charge": {
        "es": [
            ["me cobraron dos veces {amt} en {merchant}", "me cobraron dos veces la misma compra {date}", "me hicieron el cobro dos veces"],
            ["tengo un cargo duplicado de {amt}", "aparece duplicado el pago de {merchant}", "el cobro de {merchant} está duplicado"],
            ["me debitaron doble la compra de {amt}", "me descontaron doble {date}", "me cobraron doble en {merchant}"],
            ["la compra de {amt} aparece repetida en mi {card}", "me sale repetido el mismo consumo de {merchant}", "veo el mismo cargo repetido dos veces"],
            ["pagué una sola vez pero me cobraron dos, {amt} en {merchant}", "hice un solo pago y aparecen dos cargos iguales {date}"],
            ["me cargaron el mismo monto de {amt} tres veces", "hay tres cargos iguales de {merchant}"],
        ],
        "pt": [
            ["me cobraram duas vezes {amt} no {merchant}", "me cobraram duas vezes a mesma compra {date}", "fizeram a cobrança duas vezes"],
            ["tenho uma cobrança duplicada de {amt}", "o pagamento do {merchant} veio duplicado", "a cobrança do {merchant} está duplicada"],
            ["debitaram em dobro a compra de {amt}", "descontaram em dobro {date}", "cobraram em dobro no {merchant}"],
            ["a compra de {amt} aparece repetida no meu {card}", "o mesmo gasto do {merchant} aparece repetido", "vejo a mesma cobrança repetida duas vezes"],
            ["paguei uma vez só mas cobraram duas, {amt} no {merchant}", "fiz um único pagamento e aparecem duas cobranças iguais {date}"],
            ["lançaram o mesmo valor de {amt} três vezes", "tem três cobranças iguais do {merchant}"],
        ],
    },
    "wrong_amount": {
        "es": [
            ["me cobraron más de lo que era, {amt} en {merchant}", "el cobro fue mayor al precio de la compra", "me cobraron de más en {merchant} {date}"],
            ["el monto no coincide con lo que pagué", "el monto del cargo es incorrecto", "me aparece un monto distinto al del ticket de {merchant}"],
            ["tengo un cobro indebido de {amt}", "me hicieron un cobro indebido {date}", "quiero reclamar un cobro indebido en mi {card}"],
            ["me cobraron una comisión que no corresponde", "hay una comisión indebida de {amt}", "me cargaron una comisión que nunca me explicaron"],
            ["compré por {amt} y me cobraron otra cantidad", "el precio era menor y me cobraron más en {merchant}", "la cuenta era de un monto y el cargo salió más alto"],
            ["me cobraron una cuota de manejo que no debía", "me aplicaron un cargo por servicio que no corresponde de {amt}"],
            ["el cargo de {merchant} vino con un valor equivocado", "me cobraron un valor equivocado {date}"],
        ],
        "pt": [
            ["me cobraram mais do que era, {amt} no {merchant}", "a cobrança foi maior que o preço da compra", "cobraram a mais no {merchant} {date}"],
            ["o valor não bate com o que eu paguei", "o valor da cobrança está errado", "aparece um valor diferente do cupom do {merchant}"],
            ["tenho uma cobrança indevida de {amt}", "fizeram uma cobrança indevida {date}", "quero reclamar de uma cobrança indevida no meu {card}"],
            ["me cobraram uma taxa que não é devida", "tem uma tarifa indevida de {amt}", "cobraram uma taxa que nunca me explicaram"],
            ["comprei por {amt} e cobraram outro valor", "o preço era menor e cobraram mais no {merchant}", "a conta era de um valor e a cobrança veio mais alta"],
            ["me cobraram anuidade que eu não devia", "aplicaram uma tarifa de serviço indevida de {amt}"],
            ["a cobrança do {merchant} veio com o valor errado", "me cobraram um valor errado {date}"],
        ],
    },
    "not_received": {
        "es": [
            ["compré en {merchant} y nunca llegó el pedido", "pagué {amt} por un producto que nunca llegó", "mi compra {date} todavía no llega"],
            ["no recibí lo que compré en {merchant}", "no me entregaron la compra de {amt}", "nunca recibí el producto que pagué"],
            ["pagué un servicio que no me prestaron", "me cobraron {amt} por un servicio que nunca se hizo", "el servicio de {merchant} nunca se prestó"],
            ["hice un pedido {date} y la tienda no lo envió", "la tienda {merchant} cobró pero no mandó nada"],
            ["pagué una licuadora de {amt} y nunca me la entregaron", "compré un celular en línea y nunca me lo enviaron", "el paquete de {merchant} nunca apareció"],
            ["compré boletos para un evento que no se realizó y me cobraron {amt}", "reservé en {merchant} y nunca me dieron el servicio"],
        ],
        "pt": [
            ["comprei no {merchant} e o pedido nunca chegou", "paguei {amt} por um produto que nunca chegou", "minha compra {date} ainda não chegou"],
            ["não recebi o que comprei no {merchant}", "não me entregaram a compra de {amt}", "nunca recebi o produto que paguei"],
            ["paguei um serviço que não foi prestado", "me cobraram {amt} por um serviço que nunca foi feito", "o serviço do {merchant} nunca foi prestado"],
            ["fiz um pedido {date} e a loja não enviou", "a loja {merchant} cobrou mas não mandou nada"],
            ["paguei um tênis de {amt} e não chegou", "comprei um celular pela internet e nunca me enviaram", "o pacote do {merchant} nunca apareceu"],
            ["comprei ingressos para um evento que não aconteceu e cobraram {amt}", "reservei no {merchant} e nunca me deram o serviço"],
        ],
    },
    "atm_cash_not_dispensed": {
        "es": [
            ["el cajero no me dio el dinero pero me lo descontaron", "el cajero no entregó los {amt} y sí me los cobró", "saqué plata del cajero y no salió nada"],
            ["hice un retiro de {amt} {date} y el cajero no dispensó el efectivo", "el cajero automático se trabó y no me dio los billetes"],
            ["intenté retirar {amt} en el cajero, no recibí el efectivo y me debitaron", "me descontaron un retiro que el cajero nunca entregó"],
            ["el cajero me entregó menos dinero del que pedí", "pedí {amt} en el cajero y salió menos", "el cajero dio solo una parte del retiro"],
            ["fui al cajero {date}, marcó error y igual me restaron {amt}", "el ATM dio error pero el retiro aparece en mi cuenta"],
        ],
        "pt": [
            ["o caixa eletrônico não liberou o dinheiro mas descontou", "o caixa não entregou os {amt} e cobrou mesmo assim", "fui sacar no caixa e não saiu nada"],
            ["fiz um saque de {amt} {date} e o caixa não liberou as notas", "o caixa eletrônico travou e não me deu o dinheiro"],
            ["tentei sacar {amt} no caixa, não recebi e debitaram", "descontaram um saque que o caixa nunca entregou"],
            ["o caixa me entregou menos dinheiro do que pedi", "pedi {amt} no caixa eletrônico e saiu menos", "o caixa deu só uma parte do saque"],
            ["fui ao caixa {date}, deu erro e mesmo assim tiraram {amt}", "o terminal deu erro mas o saque aparece na minha conta"],
        ],
    },
    "card_lost_stolen": {
        "es": [
            ["me robaron la tarjeta", "me robaron mi {card} {date}", "me asaltaron y se llevaron la billetera con la tarjeta"],
            ["perdí mi tarjeta", "perdí la {card}", "se me perdió la tarjeta {date}"],
            ["no encuentro mi tarjeta", "extravié mi tarjeta y quiero bloquearla", "creo que dejé la tarjeta en {merchant} y ya no la tengo"],
            ["me hurtaron la cartera con mis tarjetas", "me sacaron la tarjeta del bolso", "me clonaron y robaron la tarjeta en la calle"],
            ["quiero bloquear mi tarjeta porque me la robaron", "necesito bloquear la tarjeta, la perdí", "bloqueen mi {card} que me la quitaron"],
        ],
        "pt": [
            ["roubaram meu cartão", "roubaram meu {card} {date}", "fui assaltado e levaram a carteira com o cartão"],
            ["perdi meu cartão", "perdi o {card}", "perdi o cartão {date}"],
            ["não encontro meu cartão", "extraviei meu cartão e quero bloquear", "acho que esqueci o cartão no {merchant} e não está mais comigo"],
            ["furtaram minha carteira com os cartões", "tiraram meu cartão da bolsa", "levaram meu cartão na rua"],
            ["quero bloquear meu cartão porque foi roubado", "preciso bloquear o cartão, perdi", "bloqueiem meu {card} que levaram"],
        ],
    },
    # Vague dispute messages and follow-up replies: the orchestrator treats other_in_scope as "no new type", so a
    # confident label here never overwrites the dispute type chosen earlier in the conversation.
    "other_in_scope": {
        "es": [
            ["tengo un problema con un cargo", "quiero reclamar un movimiento de mi {card}", "necesito ayuda con una transacción"],
            ["hay algo raro en mi estado de cuenta", "quiero revisar un cobro", "tengo una duda con un pago de {amt}"],
            ["quiero abrir una disputa", "quiero disputar un cargo", "necesito hacer un reclamo de mi tarjeta"],
            ["fue la segunda", "la primera", "el de ayer", "ese mismo", "el último"],
            ["sí", "sí, ese", "correcto", "exacto, ese es", "sí, confirmo"],
            ["fue de {amt}", "el de {merchant}", "fue {date}", "creo que fue {date} en {merchant}"],
            ["no, otro", "no es ese", "ninguno de esos", "no estoy seguro"],
        ],
        "pt": [
            ["tenho um problema com uma cobrança", "quero reclamar de um lançamento do meu {card}", "preciso de ajuda com uma transação"],
            ["tem algo estranho na minha fatura", "quero revisar uma cobrança", "tenho uma dúvida sobre um pagamento de {amt}"],
            ["quero abrir uma contestação", "quero contestar uma cobrança", "preciso fazer uma reclamação do meu cartão"],
            ["foi a segunda", "a primeira", "a de ontem", "essa mesma", "o último"],
            ["sim", "sim, essa", "correto", "isso, é essa", "sim, confirmo"],
            ["foi de {amt}", "a do {merchant}", "foi {date}", "acho que foi {date} no {merchant}"],
            ["não, outra", "não é essa", "nenhuma dessas", "não tenho certeza"],
        ],
    },
    "out_of_scope": {
        "es": [
            ["quiero pedir un préstamo", "cuánto me prestan", "quiero información de un crédito personal", "me interesa un crédito hipotecario"],
            ["quiero una tarjeta de crédito nueva", "cómo solicito una tarjeta de crédito", "quiero aumentar el cupo de mi tarjeta de crédito"],
            ["quiero invertir mi dinero", "qué tasa pagan los depósitos a plazo", "me interesa abrir una inversión"],
            ["quiero cambiar mi dirección", "necesito actualizar mi correo", "cómo cambio mi número de teléfono"],
            ["la app no me deja entrar", "no puedo iniciar sesión en la aplicación", "la aplicación se cierra sola"],
            ["cuál es mi saldo", "cuánto tengo disponible en mi cuenta", "a qué hora abre la sucursal"],
            ["cómo activo mi tarjeta nueva", "quiero cambiar el PIN de mi tarjeta", "cuándo llega mi tarjeta nueva"],
            ["la atención en la sucursal fue pésima", "quiero poner una queja por el servicio al cliente", "el asesor fue grosero conmigo"],
        ],
        "pt": [
            ["quero um empréstimo", "quanto vocês me emprestam", "quero informação sobre crédito pessoal", "tenho interesse em financiamento imobiliário"],
            ["quero um cartão de crédito novo", "como peço um cartão de crédito", "quero aumentar o limite do cartão de crédito"],
            ["quero investir meu dinheiro", "qual o rendimento do CDB", "tenho interesse em fazer um investimento"],
            ["quero mudar meu endereço", "preciso atualizar meu e-mail", "como troco meu número de telefone"],
            ["o app não me deixa entrar", "não consigo fazer login no aplicativo", "o aplicativo fecha sozinho"],
            ["qual é o meu saldo", "quanto tenho disponível na conta", "que horas abre a agência"],
            ["como ativo meu cartão novo", "quero trocar a senha do cartão", "quando chega meu cartão novo"],
            ["o atendimento na agência foi péssimo", "quero reclamar do atendimento ao cliente", "o atendente foi grosseiro comigo"],
        ],
    },
}

# templates-v2 (30 sep): more families per label so held-out families are not the only examples of a phrasing
# style. Written after one look at validation errors (never at test errors); see docs/ml_labels.md.
EXTRA_FAMILIES: dict[str, dict[str, list[list[str]]]] = {
    "unrecognized_charge": {
        "es": [
            ["hay una transacción en mi {card} que no me suena", "veo un débito de {amt} que desconozco", "en mi resumen hay un gasto de {merchant} que no identifico"],
            ["me llegó una notificación de compra por {amt} y yo no estaba comprando", "me avisaron de un pago en {merchant} que no fui yo"],
            ["creo que es fraude, hay un cobro de {amt} {date}", "me hackearon la tarjeta, aparece una compra en {merchant}"],
        ],
        "pt": [
            ["tem uma transação no meu {card} que eu não conheço", "vejo um débito de {amt} que desconheço", "na minha fatura tem um gasto do {merchant} que não identifico"],
            ["recebi uma notificação de compra de {amt} e eu não estava comprando", "me avisaram de um pagamento no {merchant} que não fui eu"],
            ["acho que é fraude, tem uma cobrança de {amt} {date}", "clonaram meu cartão, aparece uma compra no {merchant}"],
        ],
    },
    "duplicate_charge": {
        "es": [
            ["el mismo pago salió dos veces en mi {card}", "se procesó dos veces la compra de {merchant}", "la transacción de {amt} se duplicó"],
            ["me cobraron la suscripción de {merchant} dos veces este mes", "tengo dos débitos idénticos de {amt} {date}"],
        ],
        "pt": [
            ["o mesmo pagamento saiu duas vezes no meu {card}", "a compra do {merchant} foi processada duas vezes", "a transação de {amt} duplicou"],
            ["cobraram a assinatura do {merchant} duas vezes este mês", "tenho dois débitos idênticos de {amt} {date}"],
        ],
    },
    "wrong_amount": {
        "es": [
            ["el total cobrado no es el que acepté en {merchant}", "me cobraron {amt} pero el precio acordado era menor", "la tarifa cobrada es mayor a la publicada"],
            ["me aplicaron un recargo que no corresponde", "me cobraron intereses que no debía {date}", "hay un cargo extra de {amt} que no acepté"],
        ],
        "pt": [
            ["o total cobrado não é o que aceitei no {merchant}", "cobraram {amt} mas o preço combinado era menor", "a tarifa cobrada é maior que a anunciada"],
            ["aplicaram um acréscimo que não é devido", "cobraram juros que eu não devia {date}", "tem uma cobrança extra de {amt} que não aceitei"],
        ],
    },
    "not_received": {
        "es": [
            ["la compra de {amt} nunca me la mandaron", "no me llegó nada de lo que pagué en {merchant}", "el vendedor no entregó el pedido {date}"],
            ["pagué la reserva en {merchant} y el hotel no me recibió", "contraté un servicio de {amt} y no vinieron"],
        ],
        "pt": [
            ["a compra de {amt} nunca me mandaram", "não chegou nada do que paguei no {merchant}", "o vendedor não entregou o pedido {date}"],
            ["não recebi a compra de {amt}", "paguei a reserva no {merchant} e o hotel não me recebeu", "contratei um serviço de {amt} e não vieram"],
        ],
    },
    "atm_cash_not_dispensed": {
        "es": [
            ["retiré en el cajero de {merchant} y la plata nunca salió", "el cajero se quedó con mi dinero pero descontó {amt}"],
            ["en el cajero salió el comprobante pero no el efectivo", "el dispensador no entregó billetes {date}"],
        ],
        "pt": [
            ["saquei no caixa do {merchant} e o dinheiro nunca saiu", "o caixa ficou com meu dinheiro mas descontou {amt}"],
            ["no caixa saiu o comprovante mas não o dinheiro", "o caixa eletrônico não soltou as notas {date}"],
        ],
    },
    "card_lost_stolen": {
        "es": [
            ["me quitaron el celular y la tarjeta", "se me cayó la tarjeta en el bus y no la encuentro", "dejé olvidada mi {card} y no sé dónde está"],
            ["mi tarjeta desapareció de la billetera", "me robaron el bolso con la {card} adentro {date}"],
        ],
        "pt": [
            ["levaram meu celular e o cartão", "deixei cair o cartão no ônibus e não acho", "esqueci meu {card} e não sei onde está"],
            ["meu cartão sumiu da carteira", "roubaram minha bolsa com o {card} dentro {date}"],
        ],
    },
    "other_in_scope": {
        "es": [
            ["quiero hacer un reclamo sobre un cobro de mi tarjeta", "me pueden ayudar con un cargo de {merchant}?", "tengo una consulta sobre un movimiento de {amt}"],
            ["el segundo", "ese no", "el de {amt}", "sí, el de {merchant}", "ok"],
        ],
        "pt": [
            ["quero fazer uma reclamação sobre uma cobrança do meu cartão", "podem me ajudar com uma cobrança do {merchant}?", "tenho uma dúvida sobre um lançamento de {amt}"],
            ["o segundo", "essa não", "a de {amt}", "sim, a do {merchant}", "ok"],
        ],
    },
    "out_of_scope": {
        "es": [
            ["necesito un certificado bancario", "quiero abrir una cuenta de ahorros", "cómo hago una transferencia a otro banco"],
            ["quiero cancelar mi seguro", "quiero hablar con un asesor comercial", "tienen ofertas de tarjetas con millas?"],
        ],
        "pt": [
            ["preciso de uma declaração bancária", "quero abrir uma conta poupança", "como faço um pix para outro banco"],
            ["quero cancelar meu seguro", "quero falar com um gerente comercial", "vocês têm cartões com milhas?"],
        ],
    },
}
# templates-v3 (1 oct): eval test v1 showed the model abstaining on paraphrases of wrong_amount and not_received
# (9 of 14 errors). These families add new ways of saying those two (discounts, tips, exchange rate, unit count;
# tracking, vanished sellers, services never started, cancellations) plus one family for the other labels to keep the
# label mix. They were written after eval case set v2 was frozen (commit dc911a3) and deliberately avoid its
# phrasings, so v2 measures them; test v1 is no longer a clean held-out set for this model.
EXTRA_FAMILIES_V3: dict[str, dict[str, list[list[str]]]] = {
    "unrecognized_charge": {
        "es": [["ese consumo de {amt} no lo hice ni lo autoricé", "alguien más gastó {amt} con mi {card}", "un tercero pagó en {merchant} con mis datos"]],
        "pt": [["esse gasto de {amt} eu não fiz nem autorizei", "outra pessoa gastou {amt} com meu {card}", "um terceiro pagou no {merchant} com meus dados"]],
    },
    "duplicate_charge": {
        "es": [["en {merchant} pasaron mi tarjeta dos veces por error", "el datáfono cobró doble {amt}", "salieron dos cargos por una sola compra en {merchant}"]],
        "pt": [["no {merchant} passaram meu cartão duas vezes por engano", "a maquininha cobrou em dobro {amt}", "saíram duas cobranças por uma única compra no {merchant}"]],
    },
    "wrong_amount": {
        "es": [
            ["no me aplicaron el descuento en {merchant} y me cobraron {amt}", "la promoción decía otro precio y el cargo fue de {amt}", "me cobraron el precio completo sin la rebaja {date}"],
            ["me facturaron {amt} cuando el total era más bajo", "{merchant} me facturó mal, el monto real era menor", "el cargo de {merchant} está mal calculado"],
            ["en {merchant} me cobraron {amt} y la propina ya estaba incluida", "me pasaron un monto más alto del que firmé", "firmé el voucher por menos y aparece {amt}"],
            ["el tipo de cambio que me aplicaron en {merchant} está mal, me cobraron {amt}", "convirtieron mal la compra en dólares y pagué de más", "me cobraron una conversión de moneda exagerada {date}"],
            ["me cobraron dos unidades y compré una sola en {merchant}", "me cargaron {amt} por un artículo que costaba la mitad", "cobraron el plan más caro y yo contraté el básico"],
            ["me cobraron un excedente de {amt}", "hay una diferencia de precio en el cobro de {merchant}", "pagué de más por un error en el monto"],
        ],
        "pt": [
            ["não aplicaram o desconto no {merchant} e cobraram {amt}", "a promoção dizia outro preço e a cobrança foi de {amt}", "cobraram o preço cheio sem o desconto {date}"],
            ["faturaram {amt} quando o total era mais baixo", "o {merchant} faturou errado, o valor real era menor", "a cobrança do {merchant} está calculada errada"],
            ["no {merchant} cobraram {amt} e a gorjeta já estava incluída", "passaram um valor mais alto do que eu assinei", "assinei o comprovante por menos e aparece {amt}"],
            ["a cotação que aplicaram no {merchant} está errada, cobraram {amt}", "converteram errado a compra em dólar e paguei a mais", "cobraram uma conversão de moeda exagerada {date}"],
            ["cobraram duas unidades e comprei só uma no {merchant}", "lançaram {amt} por um item que custava a metade", "cobraram o plano mais caro e eu contratei o básico"],
            ["cobraram um excedente de {amt}", "tem uma diferença de preço na cobrança do {merchant}", "paguei a mais por um erro no valor"],
        ],
    },
    "not_received": {
        "es": [
            ["el pedido de {merchant} figura como entregado pero nunca lo recibí", "el seguimiento dice entregado y a mi casa no llegó nada", "la empresa de envíos perdió mi compra de {amt}"],
            ["el vendedor de {merchant} desapareció después de cobrarme {amt}", "pagué por adelantado y la tienda dejó de responder", "una tienda en línea me cobró y no envió nada"],
            ["pagué un curso de {amt} que nunca empezó", "contraté una suscripción en {merchant} que nunca se activó", "compré una licencia que jamás me enviaron"],
            ["cancelaron mi vuelo con {merchant} y no me devolvieron los {amt}", "el evento se suspendió y no me reintegraron la entrada", "el hotel canceló mi reserva y me cobró igual"],
            ["estoy esperando una compra de {amt} desde hace un mes", "mi pedido en {merchant} está demorado y no hay noticias", "nunca me hicieron la entrega de lo que compré {date}"],
        ],
        "pt": [
            ["o pedido do {merchant} aparece como entregue mas nunca recebi", "o rastreio diz entregue e na minha casa não chegou nada", "a transportadora perdeu minha compra de {amt}"],
            ["o vendedor do {merchant} sumiu depois de me cobrar {amt}", "paguei adiantado e a loja parou de responder", "uma loja online me cobrou e não enviou nada"],
            ["paguei um curso de {amt} que nunca começou", "assinei um serviço no {merchant} que nunca foi ativado", "comprei uma licença que nunca me enviaram"],
            ["cancelaram meu voo com {merchant} e não devolveram os {amt}", "o evento foi suspenso e não reembolsaram o ingresso", "o hotel cancelou minha reserva e cobrou mesmo assim"],
            ["estou esperando uma compra de {amt} há um mês", "meu pedido no {merchant} está atrasado e não tenho notícias", "nunca fizeram a entrega do que comprei {date}"],
        ],
    },
    "atm_cash_not_dispensed": {
        "es": [["el cajero quedó fuera de servicio a mitad del retiro y me cobró {amt}", "retiro fallido de {amt} pero descontado de mi cuenta"]],
        "pt": [["o caixa ficou fora de serviço no meio do saque e cobrou {amt}", "saque que falhou de {amt} mas descontado da minha conta"]],
    },
    "card_lost_stolen": {
        "es": [["mi tarjeta se quedó en el cajero y ya no está", "me arrancaron el teléfono con la tarjeta en la funda", "la tarjeta no aparece desde el sábado"]],
        "pt": [["meu cartão ficou no caixa eletrônico e não está mais lá", "arrancaram meu celular com o cartão na capinha", "o cartão sumiu desde sábado"]],
    },
    "other_in_scope": {
        "es": [["necesito aclarar un cargo de {merchant}", "me pueden revisar un pago de {amt}?", "tengo un reclamo pendiente por un consumo"]],
        "pt": [["preciso esclarecer uma cobrança do {merchant}", "podem verificar um pagamento de {amt}?", "tenho uma reclamação pendente por um gasto"]],
    },
    "out_of_scope": {
        "es": [["cuánto cobran por una transferencia internacional", "quiero refinanciar mi deuda", "dónde descargo mi estado de cuenta"]],
        "pt": [["quanto custa uma transferência internacional", "quero renegociar minha dívida", "onde baixo meu extrato"]],
    },
}
for _extra in (EXTRA_FAMILIES, EXTRA_FAMILIES_V3):
    for _label, _by_lang in _extra.items():
        for _lang, _fams in _by_lang.items():
            FAMILIES[_label][_lang].extend(_fams)
# Families whose members are short follow-up replies (no opener/closer is added to them).
SHORT_FAMILIES = {("other_in_scope", "es", i) for i in (3, 4, 5, 6, 8)} | {("other_in_scope", "pt", i) for i in (3, 4, 5, 6, 8)}

# ---------------------------------------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------------------------------------
MERCHANTS = ["Supermercado La Estrella", "Mercado Central", "Farmacia Salud", "Streaming Music", "Teatro Nacional",
             "Tienda Online Max", "Gasolinera Norte", "Restaurante El Puerto", "Aerolínea Sur", "Hotel Plaza",
             "Loja Bela", "Posto Ipiranga", "Magazine Brasil", "Café Aroma", "Uber", "Netflix", "Amazon", "Mercado Libre"]
CARD = {"es": ["tarjeta", "tarjeta de crédito", "tarjeta de débito", "tarjeta Visa", "Mastercard"],
        "pt": ["cartão", "cartão de crédito", "cartão de débito", "cartão Visa", "Mastercard"]}
DATES = {"es": ["hoy", "ayer", "anteayer", "el lunes", "el martes pasado", "el viernes", "el 12/06", "el 3 de enero",
                "del 23/12", "la semana pasada", "el fin de semana", "hace tres días", "este mes", ""],
         "pt": ["hoje", "ontem", "anteontem", "na segunda-feira", "na terça passada", "na sexta", "no dia 12/06",
                "em 3 de janeiro", "do dia 23/12", "semana passada", "no fim de semana", "há três dias", "este mês", ""]}
NUM_WORDS = {"es": ["cien", "doscientos", "trescientos", "quinientos", "mil", "mil quinientos", "cincuenta", "ochenta"],
             "pt": ["cem", "duzentos", "trezentos", "quinhentos", "mil", "mil e quinhentos", "cinquenta", "oitenta"]}
CURRENCY = {"es": ["", "", "$", "pesos", "dólares", "USD", "soles"], "pt": ["", "", "R$", "reais", "dólares", "USD"]}
OPENERS = {"es": ["", "", "", "hola, ", "buenas, ", "buenos días, ", "hola buenas tardes, ", "disculpe, ", "oigan, "],
           "pt": ["", "", "", "olá, ", "oi, ", "bom dia, ", "boa tarde, ", "com licença, ", "gente, "]}
CLOSERS = {"es": ["", "", "", ", me pueden ayudar?", ", qué hago?", ". Quiero reclamar", ", necesito una solución",
                  ". Mi documento es [NUMBER]", ". Soy [NAME]", ", escríbanme a [EMAIL]"],
           "pt": ["", "", "", ", podem me ajudar?", ", o que faço?", ". Quero reclamar", ", preciso de uma solução",
                  ". Meu CPF é [NUMBER]", ". Sou [NAME]", ", me escrevam em [EMAIL]"]}


def amount(rng: random.Random, lang: str) -> str:
    style = rng.random()
    if style < 0.2:
        return rng.choice(NUM_WORDS[lang]) + " " + rng.choice(["dólares", "pesos" if lang == "es" else "reais"])
    value = rng.choice([rng.randint(5, 99), rng.randint(100, 2500)]) + rng.choice([0, 0, rng.randint(1, 99) / 100])
    text = f"{value:,.2f}" if value % 1 else f"{int(value):,}"
    if rng.random() < 0.6:  # Latin American format: 1.450,50
        text = text.replace(",", "_").replace(".", ",").replace("_", ".")
    cur = rng.choice(CURRENCY[lang])
    if cur in ("$", "R$"):
        return f"{cur}{text}" if rng.random() < 0.5 else f"{cur} {text}"
    return f"{text} {cur}".strip()


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def add_typos(s: str, rng: random.Random) -> str:
    chars = list(s)
    for _ in range(rng.randint(1, 2)):
        idx = [i for i, c in enumerate(chars) if c.isalpha()]
        if len(idx) < 4:
            break
        i = rng.choice(idx)
        op = rng.random()
        if op < 0.4:
            del chars[i]
        elif op < 0.7 and i + 1 < len(chars):
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
        else:
            chars.insert(i, chars[i])
    return "".join(chars)


def fill(template: str, rng: random.Random, lang: str) -> str:
    text = template.format(amt=amount(rng, lang), date=rng.choice(DATES[lang]),
                           merchant=rng.choice(MERCHANTS), card=rng.choice(CARD[lang]))
    return re.sub(r"\s+", " ", text).strip()


def render(template: str, rng: random.Random, lang: str, short: bool) -> str:
    core = fill(template, rng, lang)
    if not short:  # follow-up replies stay short and bare, like real chat turns
        core = rng.choice(OPENERS[lang]) + core + rng.choice(CLOSERS[lang])
    r = rng.random()
    if r < 0.30:
        core = strip_accents(core)
    if rng.random() < 0.25:
        core = add_typos(core, rng)
    r = rng.random()
    if r < 0.45:
        core = core.lower()
    elif r < 0.55:
        core = core.upper()
    elif core:
        core = core[0].upper() + core[1:]
    if not short and rng.random() < 0.3:
        core += rng.choice([".", "!", "?", ""])
    # Placeholders always arrive uppercase from the backend's masking, whatever the customer's casing.
    return re.sub(r"\[(name|email|number)\]", lambda m: m.group(0).upper(), core.strip(), flags=re.I)


def mask(text: str) -> str:
    """Same placeholders as backend/internal/guard.Mask (emails and long digit runs)."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text)
    text = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[NUMBER]", text)
    return re.sub(r"\b\d[\d -]{6,}\d\b", "[NUMBER]", text)


def assign_splits(rng: random.Random) -> dict[tuple[str, str, int], str]:
    """Whole families go to one split. Per label and language: ~1/7 test, ~1/7 validation, rest train."""
    out = {}
    for label, by_lang in FAMILIES.items():
        for lang, fams in by_lang.items():
            order = list(range(len(fams)))
            rng.shuffle(order)
            n_eval = max(1, round(len(fams) / 7))
            for rank, fam in enumerate(order):
                out[(label, lang, fam)] = "test" if rank < n_eval else "val" if rank < 2 * n_eval else "train"
    return out


def transcripts_out_of_scope(rng: random.Random, max_rows: int) -> list[str]:
    try:
        import polars as pl
    except ImportError:
        return []
    files = list(TRANSCRIPTS.glob("**/*.parquet"))
    if not files:
        return []
    texts = (pl.scan_parquet([str(f) for f in files]).select("customer_text").unique().collect()
             ["customer_text"].drop_nulls().to_list())
    texts = sorted({mask(t.strip()) for t in texts if t and t.strip()})
    rng.shuffle(texts)
    return texts[:max_rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-family", type=int, default=20, help="utterances generated per template family")
    ap.add_argument("--seed", type=int, default=20260930)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    splits = assign_splits(rng)

    rows, seen = [], set()
    for label, by_lang in FAMILIES.items():
        for lang, fams in by_lang.items():
            for fam_idx, templates in enumerate(fams):
                split = splits[(label, lang, fam_idx)]
                family = f"{label}.{lang}.{fam_idx}"
                short = (label, lang, fam_idx) in SHORT_FAMILIES
                attempts = 0
                made = 0
                while made < args.per_family and attempts < args.per_family * 20:
                    attempts += 1
                    text = render(rng.choice(templates), rng, lang, short)
                    key = text.lower()
                    if not text or key in seen:
                        continue
                    seen.add(key)
                    rows.append({"text": text, "label": label, "lang": lang, "split": split,
                                 "family": family, "source": "team_generated/templates-v3"})
                    made += 1

    # Real balance-inquiry turns as out_of_scope (Spanish only; the dataset has no Portuguese text).
    real = transcripts_out_of_scope(rng, max_rows=42)
    for i, text in enumerate(real):
        split = "test" if i % 7 == 0 else "val" if i % 7 == 1 else "train"
        rows.append({"text": text, "label": "out_of_scope", "lang": "es", "split": split,
                     "family": f"out_of_scope.es.transcript{i}", "source": "silver/call_transcripts"})

    for i, r in enumerate(rows):
        r["id"] = f"u{i:05d}"
        r["sha256"] = hashlib.sha256(r["text"].encode()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "corpus.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({k: r[k] for k in ("id", "text", "label", "lang", "split", "family", "source", "sha256")},
                                ensure_ascii=False) + "\n")

    counts = Counter((r["split"], r["label"], r["lang"]) for r in rows)
    manifest = {
        "generator": "ml/data/generate_utterances.py", "templates_version": "templates-v3", "seed": args.seed,
        "per_family": args.per_family, "rows": len(rows),
        "rows_by_split": dict(Counter(r["split"] for r in rows)),
        "rows_by_split_label_lang": {f"{s}/{l}/{g}": n for (s, l, g), n in sorted(counts.items())},
        "families_by_split": {s: sorted({r["family"] for r in rows if r["split"] == s and r["source"].startswith("team")})
                              for s in ("train", "val", "test")},
        "transcript_rows": len(real),
        "corpus_sha256": hashlib.sha256("".join(r["sha256"] for r in rows).encode()).hexdigest(),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} utterances -> {OUT / 'corpus.jsonl'}")
    print("by split:", manifest["rows_by_split"], "| transcripts:", len(real))


if __name__ == "__main__":
    main()
