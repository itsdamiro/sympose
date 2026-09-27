"""The labelled messages about property values (docs/decisions/030, "Not built: property values as names"), on the
synthetic vault `tests/fixtures/properties_vault`: notes whose bodies never say the company, email, status or
policy that their properties hold, so a question about such a value is answered only if the note is found through
the property. Kept apart from `retrieval_cases.MESSAGES` so that set stays comparable with the numbers in ADR 027.
Nothing here is anyone's own data. The fields mean what they mean in `retrieval_cases.Msg`.

Groups: `value` (a value that names something, held by 1 to 3 notes: must attach exactly those), `probe` (values
held by more notes than a turn holds, or no note to name, or everyday speech that is also a value: any of `ok` may attach, and nothing else), `nothing`
(a message with no value's words in it: nothing may attach)."""

from retrieval_cases import Msg

_DANA, _OWEN, _SAM = "People/Dana Lee.md", "People/Owen Park.md", "People/Sam Ortiz.md"
_PRIYA, _LENA = "People/Priya Nair.md", "People/Lena Vogt.md"
_HARBOR, _TIDE = "Projects/Harbor Redesign.md", "Projects/Tide Tables App.md"
_BOILER, _CAR = "Home/Boiler Service.md", "Home/Car Insurance.md"
_FICTION = tuple(f"Reading/{t}.md" for t in ("The Salt Road", "Glass Winter", "Paper Kingdoms", "A Quiet Harbour", "Night Ferry", "The Long Way Round"))

_VALUE = [
    ("value", "who do I know at Northwind?", (_PRIYA,)),
    ("value", "is there anyone from Globex in my notes?", (_LENA,)),
    ("value", "which note has the email priya@northwind.example?", (_PRIYA,)),
    ("value", "which projects are on hold?", (_HARBOR, _TIDE)),
    ("value", "what is policy HM-448210?", (_CAR,)),
    ("value", "what do I have with Halden Mutual?", (_CAR,)),
    ("value", "when does Kessler Heating come next?", (_BOILER,)),
]
_ACME = "Companies/Acme.md"
_LINK = [  # a note exists for the company, and two of the three people link to it: the message names the note as well
    ("link", "who works at Acme?", (_DANA, _OWEN, _SAM), (_ACME,)),
    ("link", "which people are at Acme?", (_DANA, _OWEN, _SAM), (_ACME,)),
    ("link", "whose address is owen.park@example.org?", (_OWEN,), (_TIDE,)),  # the words "owen park" in an address also stand for the project he owns
]
_PROBE = [
    ("probe", "which of my books are fiction?", _FICTION),  # six notes hold it: a turn holds five
    ("probe", "who works at Initech?", ()),  # no note holds it
    ("probe", "I've been on hold with the bank for an hour", (_HARBOR, _TIDE)),  # a value that is also everyday speech stands for its notes (decided)
]
_NOTHING = [
    ("nothing", "what is the capital of Portugal?"),
    ("nothing", "how are you today?"),
    ("nothing", "thanks, that helps!"),
    ("nothing", "write me a haiku about autumn"),
]

PROPERTY_MESSAGES = (
    [Msg(f"{cat}-{n}", cat, text, lib=None, need=need, ok=ok, split="dev" if n % 2 == 0 else "test") for n, (cat, text, need, ok) in enumerate(_LINK, start=100)]
    + [Msg(f"{cat}-{n}", cat, text, lib=None, need=need, split="dev" if n % 2 == 0 else "test") for n, (cat, text, need) in enumerate(_VALUE)]
    + [Msg(f"{cat}-{n}", cat, text, lib=None, ok=ok, split="dev" if n % 2 == 0 else "test") for n, (cat, text, ok) in enumerate(_PROBE, start=len(_VALUE))]
    + [Msg(f"{cat}-{n}", cat, text, lib=False, split="dev" if n % 2 == 0 else "test") for n, (cat, text) in enumerate(_NOTHING, start=len(_VALUE) + len(_PROBE))]
)
