def load_dotenv(*a, **kw):
    import os
    os.environ.setdefault("DEEPSEEK_API_KEY", "sk-offline-stub")
    return True
