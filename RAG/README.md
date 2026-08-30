# 法律知识库与检索模块

这个项目的定位是“数据层 + 检索层”。

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

### 导入知识库

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


## 5. 总结

这个仓库的核心作用是：

- 生成知识库
- 导入 Chroma
- 做 RAG 检索
- 问答与法律提示
- 扫描合同风险关键词

11–16 条已经形成了较好的合同审查知识基础，但如果要做“真正的合同审查自动判定”，还需要继续补充规则判断字段和标准审查模板。

