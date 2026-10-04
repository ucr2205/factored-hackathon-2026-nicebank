# YouTube upload

**Title** (82 characters)

NiceBank: AI that settles card disputes in a minute, not 15 days | Factored Hackathon 2026

Shorter alternative (59): NiceBank — card disputes settled in a minute, not 15 days

**Thumbnail:** `thumbnail/nicebank-thumbnail.png` (1280×720)

**Description**

A cardholder sees a charge they don't recognize. Today, settling it takes about 15 days. NiceBank does it in about a minute.

NiceBank is an AI-first customer-service system for card-dispute intake, in Spanish and Portuguese. Built for the Factored AI & Data Hackathon 2026.

What it does:
• Finds the exact charge in the customer's own history from a vague description, in their currency and in USD at that day's rate.
• Explains charges that aren't final (pending, declined or reversed) instead of opening a case nobody needs.
• Opens a verified dispute, only after the customer confirms. Blocking a card asks for a second factor (TOTP).
• Hands the complete case to a specialist when it should: verified facts, actions taken, open questions.

AI proposes, code decides: a trained classifier and a language model understand the message; a versioned policy decides, and every action is verified by reading it back, audited and traced.

Results on 120 held-out cases it had never seen: 86.7% correct outcomes vs 5.8% for today's process. Zero unsafe outcomes. 26/26 manipulation attempts blocked. Median reply time 0.9 s.

Live demo: https://hackathon.evon.solutions

Chapters
0:00 The problem
0:15 Meet NiceBank
0:20 A verified dispute
0:38 Explained, not escalated · 2FA card block
1:00 Portuguese, and manipulation blocked
1:12 A specialist gets the whole case
1:38 Email notifications
1:46 Supervisor dashboard
1:53 How it works
2:18 Every turn traced
2:24 Results
2:40 Try it

NiceBank is a fictitious bank. All customer data is synthetic, from the hackathon dataset.

#AI #Banking #Fintech #LLM #Hackathon
