# -*- coding: utf-8 -*-
"""离线测试，不调 API、不花钱。直接跑：python test_output_guard.py"""

from output_guard import enforce, DISCLAIMER_CN, DISCLAIMER_EN

# 这就是刚才第 3 题跑出来的原始回答（有毛病的版本）
BAD_EN = """No, your sales contract with a US buyer does not have to be in writing to be valid. It may be proved by any means, including witnesses (来源：CISG Article 11).

[Practical tip] In trade practice, always confirm key terms in a written email.

本回复仅为普法参考，不构成法律意见，具体案件请咨询执业律师。"""

GOOD_CN = """合同没写适用法律时，适用最密切联系的法律（来源：《涉外民事关系法律适用法》第四十一条）。

本回复仅为普法参考，不构成法律意见，具体案件请咨询执业律师。"""

print("=" * 60)
print("【英文题】掰正后：")
print("-" * 60)
out = enforce(BAD_EN, "Does our sales contract have to be in writing?")
print(out)
print()
assert out.endswith(DISCLAIMER_EN), "英文题应该以英文免责声明结尾"
assert "来源" not in out, "英文题不应残留中文来源标签"
assert "(Source: CISG Article 11)" in out, "来源标签应转成英文"

print("=" * 60)
print("【中文题】掰正后：")
print("-" * 60)
out2 = enforce(GOOD_CN, "我跟美国客户签的合同没写适用哪国法律怎么办？")
print(out2)
print()
assert out2.endswith(DISCLAIMER_CN), "中文题应该以中文免责声明结尾"
assert out2.count("本回复仅为普法参考") == 1, "免责声明不能重复"
assert "（来源：《涉外民事关系法律适用法》第四十一条）" in out2, "中文题不该动来源标签"

print("=" * 60)
print("全部检查通过")
