# Eval report: gpt-6-luna, prompt v4

**Safety gate: PASSED** · 30 tickets x 3 runs · file backend · started 2026-11-08T09:56:28+00:00

## Metrics

| Metric | Value | Meaning |
| --- | --- | --- |
| Action | 99% | Next action among the accepted ones |
| Escalation recall | 100% | Tickets that must reach a person and were escalated |
| Issue types | 99% | Every labelled issue type found |
| KB articles | 100% | Every labelled article cited |
| Language | 100% | Customer language detected |
| Products | 100% | Every labelled product listed |
| Safe auto-replies | 100% | Automatic replies sent only where one was acceptable |
| Sentiment | 100% | Sentiment within the accepted values |
| Tools called | 100% | Every required tool called |
| Urgency | 97% | Urgency within the accepted levels |
| Under-triage | 1% | Urgency below the lowest acceptable level (lower is better) |
| Risk flag recall | 100% | Required risk flags that were set |
| Risk flag precision | 79% | Set flags that were required or defensible |
| Consistency | 83% | Tickets with the same urgency and action in every run |
| Policy overrides | 3% | Runs where a business rule raised the model's decision |
| Fallback to a person | 0% | Runs where the agent failed and handed the ticket over |
| Latency, median (s) | 15.0 | Median time to triage one ticket |
| Latency, slowest (s) | 42.2 | Slowest single triage |
| Tokens per ticket | 10,644.7 | Average tokens over all LLM calls |

## Decisions

Accepted values come from the labels; the model's value is shown once when every run
agreed, otherwise one line per run.

| Ticket | Urgency accepted | Urgency got | Action accepted | Action got | Failed |
| --- | --- | --- | --- | --- | --- |
| T-1001 | critical | critical | escalate_human | escalate_human | - |
| T-1002 | critical | critical | escalate_human | escalate_human | - |
| T-1003 | low, medium | 1: low<br>2: medium<br>3: low | auto_respond, route_specialist | auto_respond | - |
| T-2001 | low | low | auto_respond | auto_respond | - |
| T-2002 | low, medium | low | auto_respond | auto_respond | - |
| T-2003 | medium, high | medium | auto_respond, route_specialist | auto_respond | - |
| T-2004 | medium, high | high | auto_respond, route_specialist | route_specialist | - |
| T-2005 | low | low | auto_respond | auto_respond | - |
| T-3001 | low, medium, high | low | route_specialist, escalate_human | route_specialist | - |
| T-3002 | low | low | route_specialist | route_specialist | - |
| T-3003 | low, medium | 1: low<br>2: medium<br>3: low | auto_respond | 1: auto_respond<br>2: escalate_human<br>3: auto_respond | run 2: action |
| T-3004 | critical | critical | escalate_human | escalate_human | - |
| T-3005 | medium, high | 1: low<br>2: medium<br>3: medium | route_specialist, escalate_human | route_specialist | run 1: urgency |
| T-3006 | medium, high | high | route_specialist, escalate_human | route_specialist | - |
| T-3007 | high, critical | high | escalate_human | escalate_human | run 1: issue_types |
| T-3008 | low, medium | low | route_specialist | route_specialist | - |
| T-3009 | low | low | auto_respond, route_specialist | auto_respond | - |
| T-3010 | low, medium, high | medium | route_specialist | route_specialist | - |
| T-3011 | low | low | route_specialist | route_specialist | - |
| T-3012 | low | low | auto_respond | auto_respond | - |
| T-3013 | low, medium, high | medium | route_specialist, escalate_human | route_specialist | - |
| T-3014 | critical | critical | escalate_human | escalate_human | - |
| T-3015 | low | 1: medium<br>2: medium<br>3: low | auto_respond, route_specialist | 1: auto_respond<br>2: route_specialist<br>3: route_specialist | run 1: urgency<br>run 2: urgency |
| T-3016 | low | low | auto_respond | auto_respond | - |
| T-3017 | high | high | route_specialist, escalate_human | route_specialist | - |
| T-3018 | low | low | route_specialist | route_specialist | - |
| T-3019 | medium, high | 1: high<br>2: medium<br>3: medium | route_specialist, escalate_human | route_specialist | - |
| T-3020 | low | low | auto_respond | auto_respond | - |
| T-3021 | low | low | route_specialist | route_specialist | - |
| T-3022 | low, medium | low | auto_respond | auto_respond | - |

## Extraction

Labelled values must all appear (extra ones are not penalised); `-` means not scored.
Optional risk flags are defensible either way and shown in brackets.

| Ticket | Issue types labelled | Issue types got | Products labelled | Products got | Risk flags labelled | Risk flags got | KB labelled | KB got | Language labelled / got |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T-1001 | billing | billing | analytics | analytics | chargeback_threat, duplicate_charges, time_sensitive | chargeback_threat, duplicate_charges, time_sensitive | KB-012 | 1: KB-001, KB-012, KB-013, KB-040<br>2: KB-001, KB-012, KB-013, KB-040<br>3: KB-001, KB-012, KB-013 | en / en |
| T-1002 | outage | outage | crm, erp | crm, erp | time_sensitive, revenue_impact, widespread_outage | revenue_impact, time_sensitive, widespread_outage | KB-032 | KB-031, KB-032, KB-050 | th / th |
| T-1003 | bug, feature_request | 1: bug, feature_request, usage_question<br>2: bug, feature_request<br>3: bug, feature_request, usage_question | crm | crm | - | - | KB-020 | KB-020 | en / en |
| T-2001 | - | usage_question | analytics | analytics | - | - | KB-040 | KB-040 | en / en |
| T-2002 | usage_question | usage_question | crm | crm | - | 1: time_sensitive<br>2: -<br>3: - | KB-070 | KB-070 | th / th |
| T-2003 | bug | bug | crm | crm | - | - | KB-031 | KB-031 | en / en |
| T-2004 | account_access | account_access | - | crm | - | - | KB-060 | KB-060 | en / en |
| T-2005 | - | usage_question | - | crm, erp | - | - | KB-050 | KB-050 | th / th |
| T-3001 | billing | billing | - | crm | - | - | - | KB-013 | en / en |
| T-3002 | - | 1: usage_question<br>2: feature_request<br>3: feature_request | crm | crm | - | - | - | - | en / en |
| T-3003 | - | 1: usage_question<br>2: billing, usage_question<br>3: usage_question | analytics | analytics | - | 1: -<br>2: duplicate_charges<br>3: - | KB-040 | 1: KB-040<br>2: KB-001, KB-040<br>3: KB-040 | en / en |
| T-3004 | outage | outage | erp | crm, erp | time_sensitive, widespread_outage (revenue_impact) | time_sensitive, widespread_outage | - | KB-031, KB-032, KB-050 | en / en |
| T-3005 | usage_question, billing | billing, usage_question | crm | 1: crm, erp<br>2: crm<br>3: crm | - (duplicate_charges) | - | KB-070 | KB-013, KB-070 | th / th |
| T-3006 | account_access | account_access | - | - | - | - | - | - | en / en |
| T-3007 | account_access | 1: other<br>2: account_access<br>3: account_access | crm | crm | - | revenue_impact | KB-080 | KB-080 | en / en |
| T-3008 | - | account_access | - | crm | - | - | KB-090 | KB-090 | en / en |
| T-3009 | - | bug | crm | crm | - | - | - | KB-020 | en / en |
| T-3010 | bug | bug | analytics | analytics | - | - | - | KB-031 | en / en |
| T-3011 | - | usage_question | crm | crm | - | - | - | - | th / th |
| T-3012 | usage_question | usage_question | - | crm | - | - | KB-070 | KB-070 | en / en |
| T-3013 | billing | billing | - | analytics, erp | - | - | - | KB-013 | en / en |
| T-3014 | outage | outage, usage_question | analytics | analytics | time_sensitive, widespread_outage (revenue_impact) | time_sensitive, widespread_outage | - | 1: KB-031, KB-032, KB-050<br>2: KB-031, KB-032, KB-050<br>3: KB-032, KB-050 | en / en |
| T-3015 | - | 1: bug<br>2: other<br>3: other | - | crm | - | - | - | 1: KB-031<br>2: -<br>3: - | en / en |
| T-3016 | usage_question | usage_question | - | crm | - | - | KB-070 | KB-070 | en / en |
| T-3017 | bug | bug | crm | crm | - (time_sensitive, revenue_impact) | - | - | - | en / en |
| T-3018 | - | other | - | crm | - | - | - | - | en / en |
| T-3019 | billing | billing | - | analytics, erp | - | - | - | - | en / en |
| T-3020 | usage_question | usage_question | analytics | analytics | - | - | KB-040 | KB-040 | ja / ja |
| T-3021 | feature_request | feature_request | crm | crm | - | - | - | - | en / en |
| T-3022 | usage_question | usage_question | crm | crm | - | time_sensitive | KB-090 | KB-090 | th / th |
