from llm import ask

PROVISIONS = [
      {
          "source": "《涉外民事关系法律适用法》第四十一条",
          "text": "当事人可以协议选择合同适用的法律。当事人没有选择的，适用履行义务最能体现该合同特征的一方当事人经常居所地法律或者其他与该合同有最密切联系的法律。",
      },
      {
          "source": "CISG Article 11",
          "text": "A contract of sale need not be concluded in or evidenced by writing and is not subject to any other requirement as to form. It may be proved by any means,including witnesses.",
      },
]

QUESTIONS = [
      "我跟美国客户签的合同里没写用哪国法律，将来打官司怎么算？",
      "我想在美国注册商标，流程是什么？",
      "Does our sales contract with a US buyer have to be in writing to be valid?",
]

for q in QUESTIONS:
    print("=" * 60)
    print("问：" + q)
    print("-" * 60)
    print(ask(q, PROVISIONS))
    print()