# Offline stand-in for the openai SDK: no network, no cost.
# It just returns pre-scripted replies. For tests only.
REPLIES = []   # push replies in before a test; taken in order
SENT = []      # every messages payload that was "sent", for assertions


class _Msg:
    def __init__(self, c): self.content = c


class _Choice:
    def __init__(self, c): self.message = _Msg(c)


class _Resp:
    def __init__(self, c): self.choices = [_Choice(c)]


class _Completions:
    def create(self, model=None, messages=None, temperature=None, **kw):
        SENT.append(messages)
        return _Resp(REPLIES.pop(0) if REPLIES else "(no scripted reply left)")


class _Chat:
    def __init__(self): self.completions = _Completions()


class OpenAI:
    def __init__(self, *a, **kw): self.chat = _Chat()
