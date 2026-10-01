"""What compaction (docs/decisions/055) says to the model: the request that writes the notes, and the
label the notes carry in the system prompt. As with the recap, the notes are written from the user's
own messages only: the persona's replies include what she got wrong or made up, and notes that record
them make them "what the user said" (measured, docs/decisions/055)."""

NOTES_LABEL = (
    "Earlier in this conversation (the first part was condensed to save room). These notes are from the "
    "user's own messages, so they do not include what you said, and they are not notes from the vault:"
)

INSTRUCTIONS = (
    "You keep short notes on the user's side of a long conversation, so the user's assistant can carry on "
    "after the oldest messages are removed to save room. You are given the notes so far (or NONE) and then "
    "the user's own newer messages, in order. Write the updated notes: in at most 150 words of plain "
    "sentences, with no headings or lists, say what the user is working on or asking about, what they "
    "stated or decided (names, numbers and dates exactly as written), and what is still open. Keep what "
    "still matters from the notes so far and add what the new messages show. Use only what the notes and "
    "the messages say and never invent anything. Output only the notes."
)
