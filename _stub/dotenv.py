# 假的 python-dotenv 替身，让测试不用真的 .env 也能跑。
def load_dotenv(*a, **kw):
    import os
    os.environ.setdefault("DEEPSEEK_API_KEY", "sk-offline-stub")
    return True


# chromadb 启动时会 from dotenv import dotenv_values。
# 少了它，测试里 import chromadb 会失败，检索被迫退回全量扫描，
# 等于测试根本没覆盖到向量库那条路。补上，别让替身挡了真东西的路。
def dotenv_values(*a, **kw):
    return {}


def find_dotenv(*a, **kw):
    return ""


def set_key(*a, **kw):
    return (True, "", "")
