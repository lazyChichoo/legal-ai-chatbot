# -*- coding: utf-8 -*-
"""
试真接口.py —— 用真的 DeepSeek 打几次，确认接口通不通、答案能不能看、防线会不会误杀。

跑法（在仓库目录下，.env 要在同一个目录）：
    python 试真接口.py

之前所有测试用的都是 _stub 里的"假 AI"，测的是 prompt 和防线的逻辑。
这个脚本相反：它不碰 _stub，走真接口，花的是真钱（三题加起来不到一分钱）。
"""
import io
import os
import sys
import time

# 万一 _stub 还留在 sys.path 上（比如被 PYTHONPATH 指过去），这里要把它踢掉，
# 否则打的还是假接口，白测。
sys.path = [p for p in sys.path if "_stub" not in p.replace("\\", "/")]

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def line(ch="=", n=62):
    print(ch * n)


# ---------- 第 0 步：环境自检，别打了接口才发现 key 没读到 ----------
line()
print("第 0 步：环境自检")
line()

try:
    import openai
    print("  openai SDK 版本：%s" % getattr(openai, "__version__", "未知"))
    print("  SDK 来自：%s" % os.path.dirname(getattr(openai, "__file__", "?")))
    if "_stub" in getattr(openai, "__file__", ""):
        print("  !! 这是假接口替身，不是真 SDK。停。")
        sys.exit(1)
except ImportError:
    print("  !! 没装 openai。先跑：python -m pip install openai")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("  !! 没装 python-dotenv。先跑：python -m pip install python-dotenv")
    sys.exit(1)

key = os.environ.get("DEEPSEEK_API_KEY", "")
if not key:
    print("  !! 没读到 DEEPSEEK_API_KEY。")
    print("     检查当前目录下有没有 .env 文件，里面应该有一行：")
    print("     DEEPSEEK_API_KEY=sk-xxxxxxxx")
    print("     当前目录：%s" % os.getcwd())
    sys.exit(1)
# 只露头尾，中间打码，免得截图发群里泄露
masked = key[:6] + "*" * max(0, len(key) - 10) + key[-4:] if len(key) > 10 else "***"
print("  读到 key：%s（长度 %d）" % (masked, len(key)))

if key.startswith("sk-offline"):
    print("  !! 这是替身用的假 key，不是真的。停。")
    sys.exit(1)

print("  当前目录：%s" % os.getcwd())
print("  OK，开打。\n")

import bot   # noqa: E402  放这儿是故意的：自检没过就不该 import，import 会直接连 key

# ---------- 第 1 步：三道真题 ----------
CASES = [
    ("中文·知识库内",
     "美国买方收到货后说质量不合格要退货，但已经过去三个月了，我还能拒绝吗？"),
    ("英文·知识库内",
     "The US buyer rejected my goods claiming non-conformity. "
     "Is there a time limit for the buyer to give notice?"),
    ("中文·知识库外（应该拒答）",
     "我想在美国注册一家公司做跨境电商，选特拉华州还是加州更好？"),
]

results = []
for tag, q in CASES:
    line()
    print("【%s】" % tag)
    print("问：%s" % q)
    line("-")
    t0 = time.time()
    try:
        info = bot.answer_detailed(q)
    except Exception as e:
        print("  !! 打接口炸了：%s: %s" % (type(e).__name__, e))
        results.append((tag, "炸了", str(e)[:80]))
        print()
        continue
    dt = time.time() - t0

    print("检索到的条文：%s" % (
        "、".join("第%s条" % p["no"] for p in info["provisions"]) or "（一条都没检索到）"))
    print("有没有真打接口：%s" % ("打了" if info["called_api"] else "没打，直接拒答"))
    print("耗时：%.1f 秒" % dt)

    tr = info["trace"]
    if tr:
        blocked = [t for t in tr if not t["passed"]]
        if blocked:
            print("防线拦截：拦了 %d 次" % len(blocked))
            for t in blocked:
                for p in t["problems"]:
                    print("   - %s" % p)
                # 被拦下的原话要打出来，否则只看拦截理由没法判断是真拦对了还是误杀
                if t.get("raw"):
                    print("   ┌─ 第 %s 轮被拦下的原话 ─" % t["round"])
                    for ln in t["raw"].splitlines():
                        print("   │ " + ln)
                    print("   └────────────────────")
        else:
            print("防线拦截：一次都没拦（第一轮就合格）")

    print("\nAI 回答：")
    print(info["answer"])
    print()
    results.append((tag, "通", "拦%d次" % len([t for t in tr if not t["passed"]])))

# ---------- 第 2 步：小结 ----------
line()
print("小结")
line()
for tag, st, note in results:
    print("  %-22s %s  %s" % (tag, st, note))
line()
print("要看的三件事：")
print("  1. 三题都'通'   —— 接口和 key 没问题")
print("  2. 前两题答案里有（来源：…）和免责声明 —— prompt 和防线在真答案上也管用")
print("  3. 第三题回的是'超出当前知识库范围' —— 不会瞎编")
line()
