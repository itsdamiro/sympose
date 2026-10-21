"""Socket Mode payloads as Slack documents them (the `payload` of an `events_api` envelope), for the Slack tests."""

BOT = "U0BOT"
OWNER = "U0OWNER"


def dm(text="hello", user=OWNER, ts="1700000001.000100", event_id="Ev1", **more):
    event = {"type": "message", "channel_type": "im", "channel": "D0DM", "user": user, "text": text, "ts": ts,
             "event_ts": ts, "client_msg_id": "c1", **more}
    return {"type": "event_callback", "event_id": event_id, "event": event}


def mention(text=f"<@{BOT}> what is in my notes?", user=OWNER, ts="1700000002.000200", thread_ts=None, event_id="Ev2"):
    event = {"type": "app_mention", "channel": "C0CHAN", "user": user, "text": text, "ts": ts, "event_ts": ts,
             **({"thread_ts": thread_ts} if thread_ts else {})}
    return {"type": "event_callback", "event_id": event_id, "event": event}
