"""Renders the ticket and customer profile into the agent's first message."""

from datetime import UTC

from triage.models import CustomerProfile, Ticket


def render_ticket_context(ticket: Ticket, customer: CustomerProfile | None) -> str:
    profile = (
        customer.model_dump_json(indent=2)
        if customer
        else f'{{"customer_id": "{ticket.customer_id}", "note": "profile not found"}}'
    )
    thread = "\n".join(
        f"[{m.sent_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC] {m.author}: {m.content}"
        for m in ticket.messages
    )
    now = ticket.messages[-1].sent_at.astimezone(UTC)
    return (
        f"<customer_profile>\n{profile}\n</customer_profile>\n\n"
        f'<ticket id="{ticket.ticket_id}">\n{thread}\n</ticket>\n\n'
        f"Current time: {now:%Y-%m-%d %H:%M} UTC (time of the latest message)."
    )
