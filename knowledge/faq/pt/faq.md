# Perguntas frequentes — contestações de cartão

> Conteúdo de exemplo criado pela equipe para o hackathon a partir de `policies/disputes.yaml` (v0.2.0). Não é a política de um banco real.

## O que posso fazer com o assistente?
<!-- covers: policy:rule:SCOPE-01 -->
Você pode contestar uma cobrança do cartão que não reconhece, uma cobrança duplicada, um valor incorreto, uma compra que não recebeu ou um saque em caixa eletrônico que não liberou o dinheiro. Também pode comunicar um cartão perdido ou roubado. Para empréstimos, investimentos ou mudança de dados, use o aplicativo ou uma agência.

## Quanto tempo tenho para contestar uma cobrança?
<!-- covers: policy:dispute_type:unrecognized_charge policy:dispute_type:atm_cash_not_dispensed -->
Até 120 dias a partir da data da transação. Para um saque em caixa eletrônico que não liberou o dinheiro, até 60 dias. Se a transação for mais antiga, o assistente passa o caso a um especialista.

## O assistente abre a contestação sozinho?
<!-- covers: policy:globals -->
Ele procura a transação nos seus registros, mostra o que encontrou e pede sua confirmação. Só depois que você confirma ele abre o caso, e verifica que ficou registrado.

## Até que valor o assistente resolve?
<!-- covers: policy:dispute_type:unrecognized_charge policy:dispute_type:wrong_amount policy:dispute_type:duplicate_charge policy:dispute_type:not_received policy:dispute_type:atm_cash_not_dispensed -->
Ele abre o caso automaticamente até 500 USD em cobranças não reconhecidas ou com valor incorreto, 1.000 USD em cobranças duplicadas e 300 USD em compras não recebidas ou saques. Acima desses valores, o caso vai para um especialista. Os valores são comparados em dólares com o câmbio do dia da transação.

## Roubaram ou perdi meu cartão, o que faço?
<!-- covers: policy:dispute_type:card_lost_stolen -->
Escreva para o assistente. Ele vai propor bloquear o cartão e passar o caso para a equipe de fraude. Para bloquear, ele vai pedir o código do seu app autenticador.

## Vejo uma cobrança que já foi estornada, preciso contestar?
<!-- covers: policy:explain:EXPLAIN-REVERSED -->
Não. Se a cobrança já foi estornada, o dinheiro voltou para sua conta e não é preciso abrir uma contestação.

## A compra que eu não fiz aparece como recusada, fui cobrado?
<!-- covers: policy:explain:EXPLAIN-DECLINED-FRAUD policy:explain:EXPLAIN-DECLINED -->
Nada foi cobrado. Mas, se não foi você, alguém pode ter tentado usar seu cartão: o assistente vai propor bloquear o cartão e passar o caso para a equipe de fraude.

## A cobrança ainda está pendente, posso contestar?
<!-- covers: policy:explain:EXPLAIN-PENDING -->
Se você reclama de um valor incorreto, de uma compra não recebida ou de um caixa que não liberou o dinheiro, espere a cobrança ser confirmada: uma cobrança pendente ainda pode mudar ou sumir. Se você não reconhece a cobrança, pode contestá-la mesmo pendente.

## E se eu já abri uma contestação para essa mesma transação?
<!-- covers: policy:rule:DISP-DUPCASE-01 -->
O assistente informa o número do caso existente e não abre outro.

## Que dados o assistente precisa para encontrar a transação?
<!-- covers: policy:rule:CLARIFY-NOTFOUND policy:rule:CLARIFY-MULTI policy:rule:ESC-CLARIFY-LIMIT -->
Ajuda muito informar o valor e a data, ou o estabelecimento. Se houver várias transações parecidas, ele mostra até 5 para você escolher. Se depois de 2 tentativas não conseguir identificar, passa o caso a um especialista.

## O assistente pode devolver meu dinheiro ou fazer uma transferência?
<!-- covers: policy:globals -->
Não. O assistente nunca reembolsa dinheiro, nunca transfere fundos e nunca mostra dados de outro cliente. Ele abre sua contestação ou encaminha para um especialista, que é quem resolve.

## E se o sistema falhar?
<!-- covers: policy:rule:ESC-TECH-01 -->
Se algo técnico não responder, o assistente passa seu caso a um especialista para que você não fique sem resposta.

## Onde vejo o andamento das minhas contestações?
Na seção «Minhas contestações» do aplicativo você vê cada contestação aberta e cada caso com um especialista, com o seu status. Quando um especialista encerra o caso, ali aparece o resultado e a explicação.

## Quanto tempo dura a conversa?
<!-- covers: policy:globals -->
A conversa é encerrada após 15 minutos sem atividade. Você pode começar uma nova quando quiser.
