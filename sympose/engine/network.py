"""How Sympose reaches a model over the network (docs/decisions/040, "Measured"; amended 2026-10-06).

Python tries a host's addresses one at a time, and where the network has a dead IPv6 route (no answer, not a refusal)
each of the host's several IPv6 addresses costs its whole connect wait before the IPv4 one is tried. On the machine this
was found on, a one-word reply from a cloud model took 124 s that way and 1.6 s over IPv4, with the same prompt.
So model and embedding calls use IPv4 only. A network that has only IPv6 can turn that off with
`SYMPOSE_ALLOW_IPV6=1`."""

import os

import litellm

ALLOW_IPV6 = "SYMPOSE_ALLOW_IPV6"


def prefer_ipv4() -> None:
    """Make every litellm call (chat and embeddings) connect over IPv4, unless the user allows IPv6."""
    litellm.force_ipv4 = os.environ.get(ALLOW_IPV6, "").strip().lower() not in ("1", "true", "yes", "on")

