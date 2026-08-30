# 法律知识库与检索模块

这个项目的定位是“数据层 + 检索层”，不是完整的 Web/API 服务。

它主要负责：

- 读取法律知识条目
- 规范化知识字段
- 把知识写入 Chroma 向量库
- 根据用户问题做 RAG 检索
- 返回最相关的法律知识和风险提示


## 1. 各个文件的职责

### ingest.py

负责知识导入：

- 读取 JSON / JSONL / CSV / DOCX / TXT
- 解析知识字段
- 校验 category 是否属于：实体救济 / 合同审查 / 程序应急
- 对每条知识切块
- 调用 embedding 生成向量
- 写入 Chroma

### retrieve.py

负责检索和召回：

- 根据用户问题调用 Chroma 查询
- 结合关键词重叠度和向量距离排序
- 返回最相关知识条目
- 评估考卷命中率
- 扫描合同里的关键法律词

### chat.py

负责命令行问答：

- 接收用户输入
- 调用 retrieve()
- 输出相关法律知识

### contract_check.py

负责合同扫描：

- 读取合同文本
- 扫描常见法律关键词
- 输出命中结果

### legal_knowledge_20.json

当前示例知识库，包含 20 条结构化知识条目，供导入 RAG 索引使用。

### requirements.txt

Python 依赖，当前用于安装 ChromaDB。


## 2. 如何生成 RAG

### 第一步：准备知识源

建议使用结构化 JSON，字段至少包含：

- id
- title
- article
- scenario
- category
- keywords
- risk_level
- typical_question
- answer
- legal_basis
- review_points
- risk_warning

例如：

```json
[
  {
    "id": "demo-001",
    "title": "无理由拒收",
    "article": "收货方无正当理由拒收的，应保存送达、催收及现场记录。",
    "scenario": "买方拒收已按约交付的货物",
    "category": "程序应急",
    "keywords": ["拒收", "交付", "损失赔偿"],
    "risk_level": "高风险",
    "typical_question": "买方无理由拒收货物，我能怎么维护权利？",
    "answer": "应及时保全送达、催收和现场记录，并依据合同约定主张继续履行或损失赔偿。",
    "legal_basis": "UCC §2-703；CISG Art.61",
    "review_points": "检查拒收是否有正当理由、送达证据和催告记录。",
    "risk_warning": "若仅口头沟通拒收，举证将很困难。"
  }
]
```

### 第二步：导入知识库

```bash
python ingest.py --source legal_knowledge_20.json --db ./legal_knowledge_db --collection legal_knowledge --reset
```

如果想导入整个目录：

```bash
python ingest.py --source . --db ./legal_knowledge_db --collection legal_knowledge --reset --allow-fewer
```

执行后会发生：

1. 读取知识源
2. 按字段切块
3. 生成 embedding
4. 写入 Chroma

这一步就是 RAG 的建库过程。

### 第三步：启动问答

```bash
python chat.py --db ./legal_knowledge_db --collection legal_knowledge --top-k 3
```

输入问题后，系统会：

1. 把问题也做 embedding
2. 在 Chroma 中按相似度查找候选知识
3. 按关键词重叠度 + 距离排序
4. 返回最相关知识

### 第四步：评测命中率

```bash
python -c "from retrieve import evaluate_exam; print(evaluate_exam('考卷1.0.docx', db_path='./legal_knowledge_db', collection_name='legal_knowledge', top_k=5, tag_weight=0.25))"
```


## 3. 11–16 条是否实现了“合同审查功能”

结论：已经“实现了知识层的合同审查能力”，但还没有完全实现“自动化合同审查器”。

### 已实现的内容

11–16 条覆盖了典型合同审查问题，例如：

- 11：仲裁条款
- 12：违约金缺失风险
- 13：检验期 / 异议期
- 14：所有权保留
- 15：法律适用
- 16：不可抗力条款

这些知识条目已经具备：

- 场景描述
- 审查点
- 风险提示
- 法律依据
- 相关问法

因此，它们已经可以用于“检索和提示”，属于合同审查知识库。

### 还需要完善的部分

但它还不能直接做到：

- 读取一份完整合同文本
- 自动判断某个条款是否缺失
- 输出明确的“通过 / 警告 / 失败”结论

当前更准确的说法是：

- 这是“合同审查知识库 + RAG 检索”
- 还不是“自动化合同审查规则引擎”

如果要继续完善，建议增加：

- 缺失条款关键词列表
- 风险判定字段，例如 pass / warning / fail
- 标准条款模板
- 结论模板，例如“缺失仲裁条款，属于中风险”


## 4. 不建议上传数据库

不要把 `legal_knowledge_db/` 直接提交到 GitHub。它属于生成产物，不是源码。

推荐做法：

- 上传知识源文件（JSON / DOCX / TXT）
- 上传代码
- 不上传 Chroma 数据库目录

这样其他人可以从原始知识源重新生成 RAG 索引。


## 5. 总结

这个仓库的核心作用是：

- 生成知识库
- 导入 Chroma
- 做 RAG 检索
- 问答与法律提示
- 扫描合同风险关键词

11–16 条已经形成了较好的合同审查知识基础，但如果要做“真正的合同审查自动判定”，还需要继续补充规则判断字段和标准审查模板。

## 9. 协作说明

本仓库适合承担“数据与检索”职责，目标是：

- 维护知识库
- 处理知识导入和切块
- 提供精准召回结果
- 供 API 层再封装成服务接口

因此，后续 API 组的工作应集中在：

- HTTP 接口包装
- 参数校验
- 返回 JSON 规范
- 权限、鉴权和日志
- 前后端联调

而不是重复实现知识导入和召回逻辑。


## 10. 常见问题

### Q: 为什么导入后检索不到内容？

- 是否已执行 `ingest.py`
- 数据文件是否被正确识别
- `category` 是否为 `实体救济` / `合同审查` / `程序应急` 中的一种
- 是否含有 `article` 和 `scenario`

### Q: 是否可以直接上传数据库？

不建议。更好的做法是上传知识源，随后在本地重新生成数据库。


## 11. 结论

本仓库更适合定位为“法律知识库数据与检索模块”，而不是完整应用服务。它提供的核心价值是：

- 结构化知识管理
- RAG 检索
- 法律规则召回
- 合同关键词扫描

后续 API 组可以直接基于它实现接口封装、服务治理和业务接入。

## 2. 项目结构

```text
.
├── chat.py                 # 交互式问答入口
├── contract_check.py       # 合同扫描入口
├── ingest.py               # 导入知识库到 Chroma
├── retrieve.py             # 检索、评分、考卷评估
├── requirements.txt        # Python 依赖
├── materials.demo.json     # 示例知识库 JSON
├── legal_knowledge_db/     # 本地 Chroma 数据库
├── 考卷1.0.docx            # 评测文档示例
├── 考卷1.0（长问法版).docx  # 评测文档示例
├── README.md               # 项目说明
└── .gitignore              # 忽略生成文件
```


## 3. 技术栈

- Python 3.10+
- ChromaDB
- 纯 Python 规则 embedding（无需 OpenAI / embedding API）
- 关键词 + 向量召回混合排序


## 4. 环境准备

在项目根目录执行：

```bash
python -m pip install -r requirements.txt
```

如果你在 Windows 环境中使用已安装的 Python 环境，也可以直接使用：

```powershell
E:/anaconda_envs/lantestwork/python.exe -m pip install -r requirements.txt
```


## 5. 复现步骤

### 5.1 准备知识源

支持以下文件形式：

- JSON
- JSONL
- CSV
- DOCX
- TXT

推荐直接使用结构化知识条目文件，例如：

- `materials.demo.json`
- 或者自定义 DOCX / TXT 模板，字段遵循如下结构：

```json
[
  {
    "id": "demo-011",
    "title": "仲裁条款",
    "article": "仲裁条款应明确仲裁机构或可确定的仲裁机构。",
    "scenario": "审查合同争议解决条款",
    "category": "合同审查",
    "keywords": ["仲裁", "争议解决", "送达"],
    "risk_level": "中风险",
    "typical_question": "合同没有仲裁条款怎么办？",
    "answer": "卖方有权要求仲裁并保留证据。",
    "legal_basis": "CISG Art.61",
    "review_points": "确认仲裁机构和送达方式。",
    "risk_warning": "未约定仲裁可能延误救济。"
  }
]
```

如果使用 DOCX / TXT 模板，则字段应类似：

```text
【编号】第11条
【标题】合同没写"买方拒收时卖方可转售"——缺救济条款的风险
【场景标签】合同审查
【风险等级】高风险
【典型问法】合同里只写了买方权利，没写我作为卖家拒收后能干嘛，有什么风险？
【回答】...
【法律依据】...
【合同审查点】...
【关键词】...
【风险提示】...
```


### 5.2 导入知识库到 Chroma

如果你已经准备好了知识文件，可以执行：

```bash
python ingest.py --source . --db ./legal_knowledge_db --collection legal_knowledge --reset --allow-fewer
```

说明：

- `--source .` 会读取当前目录下所有匹配的知识文件；
- `--reset` 会清空原有集合后重建；
- `--allow-fewer` 允许少量文件时仍执行导入；
- 如果你只想导入单个文件，可以写成：

```bash
python ingest.py --source "知识库11-20条.docx" --db ./legal_knowledge_db --collection legal_knowledge --reset --allow-fewer
```

建议在真实使用时，将知识文件放到单独的目录中，例如：

```text
knowledge/
  - 规则库1.docx
  - 规则库2.json
```

然后执行：

```bash
python ingest.py --source ./knowledge --db ./legal_knowledge_db --collection legal_knowledge --reset
```

这样更稳定，不容易把考卷文件也一起导入。


### 5.3 启动问答助手

```bash
python chat.py --db ./legal_knowledge_db --collection legal_knowledge --top-k 3
```

随后输入问题即可，例如：

```text
买方拒收后卖方如何转售和追偿？
合同里没有违约金条款风险是什么？
```


### 5.4 合同扫描

```bash
python contract_check.py --file contract.txt --terms "中英法律术语对照表.xlsx"
```

或者直接传入文本：

```bash
python contract_check.py "合同里写了违约金，但没有明确违约金比例。"
```


### 5.5 评测考卷命中率

可直接运行：

```bash
python -c "from retrieve import evaluate_exam; print(evaluate_exam('考卷1.0.docx', db_path='./legal_knowledge_db', collection_name='legal_knowledge', top_k=5, tag_weight=0.25))"
```

或者：

```bash
python -c "from retrieve import evaluate_exam; print(evaluate_exam('考卷1.0（长问法版).docx', db_path='./legal_knowledge_db', collection_name='legal_knowledge', top_k=5, tag_weight=0.25))"
```

输出中会返回：

- total：题目总数
- hits：命中数
- accuracy：命中率


## 6. 重要说明：不建议上传数据库

这个项目的数据库目录 `legal_knowledge_db` 是生成物，通常不需要提交到 GitHub。因为：

- 它依赖本地 Chroma 索引
- 它是构建产物而不是源码
- 其他人可以从原始知识文件重新生成
- 这样更容易复现和管理版本

推荐做法：

- 上传源码
- 上传知识源文件（JSON / DOCX / TXT）
- 不上传 `legal_knowledge_db/`


## 7. GitHub 推荐设置

建议在仓库中添加 `.gitignore`，忽略：

```gitignore
legal_knowledge_db/
*.sqlite3
__pycache__/
*.pyc
```

这样其他人拉取代码后，自己执行导入命令即可重建数据库。


## 8. 常见问题

### Q: 为什么导入后检索不到内容？

检查以下几点：

- 是否已执行 `ingest.py`
- 数据文件是否被正确识别
- `category` 是否为 `实体救济` / `合同审查` / `程序应急` 中的一种
- 是否含有 `article` 和 `scenario`

### Q: 为什么考卷命中率很低？

可能原因：

- 知识库没有重建
- 导入的源文件过多，混入了考卷或无关文件
- 规则内容不够完整
- 文本分块太短或太长

### Q: 是否可以直接上传数据库？

不建议。更好的做法是上传知识源，将数据库在本地重新生成。


## 9. 结论

该项目适合“源码 + 知识源 + 运行脚本”的公开复现方式。只要别人拿到代码和知识文件，重新运行导入命令，就能恢复同样的检索和问答体验。

如果你准备把它放到 GitHub，推荐提交：

- 代码文件
- README
- 知识源文件
- `.gitignore`

不提交：

- `legal_knowledge_db/`


## 10. 快速开始命令

```bash
python -m pip install -r requirements.txt
python ingest.py --source ./knowledge --db ./legal_knowledge_db --collection legal_knowledge --reset
python chat.py --db ./legal_knowledge_db --collection legal_knowledge --top-k 3
```

如果你已经有现成知识源文件，也可以直接用：

```bash
python ingest.py --source "知识库11-20条.docx" --db ./legal_knowledge_db --collection legal_knowledge --reset --allow-fewer
```
