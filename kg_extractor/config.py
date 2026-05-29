"""
Knowledge graph extraction config for 毛泽东年谱 chronology.
"""

import os

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-v4-flash"

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries
CONCURRENCY = 3

CHECKPOINT_FILE = "../data/graph/checkpoint.json"
NODES_FILE = "../data/graph/nodes.jsonl"
EDGES_FILE = "../data/graph/edges.jsonl"

INPUT_JSONL = "../data/mao-chronology.jsonl"

SYSTEM_PROMPT = """你是一个知识图谱构建专家。你的任务是从毛泽东年谱的时序条目中提取实体和关系。

## 实体类型

- person: 人物 (毛泽东, 周恩来, 蔡和森, 萧子升...)
- organization: 组织机构 (中共中央, 国务院, 中央军委, 新民学会...)
- location: 地点 (长沙, 北京, 延安, 韶山, 岳麓山...)
- event: 事件 (会议, 战役, 运动, 成立大会...)
- document: 文献 (电报, 信件, 文章, 社论, 报告...)
- date: 时间 (仅在原文中出现具体日期时提取，如"翌年""三天后")

## 关系类型

- attended: 人物出席事件
- presided: 人物主持事件
- sent_to: 人物致电/致信人物或组织
- wrote: 人物撰写文献
- met_with: 人物会见人物
- discussed_with: 人物与人物讨论
- ordered: 人物指示组织或人物
- approved: 人物批准文献
- located_in: 事件发生在地点
- travels_to: 人物前往地点
- mentioned_in: 实体在文献中被提及

## 输出格式

返回一个JSON对象，包含nodes和edges两个数组：

```json
{
  "nodes": [
    {"id": "n001", "type": "person", "name": "毛泽东", "aliases": []},
    {"id": "n002", "type": "event", "name": "新民学会成立大会", "date": "1918-04-14"}
  ],
  "edges": [
    {"source": "n001", "target": "n002", "type": "attended", "evidence": "出席在长沙岳麓山召开的新民学会成立大会"}
  ]
}
```

## 规则

1. 只提取在文本中明确出现的实体，不要推测。
2. 实体名称使用规范名称，不要使用简称（如用"中共中央"而非"中央"）。
3. 毛泽东本人始终包含在实体中（如果他在事件中出现）。
4. 如果文本中没有可提取的关系，返回空的nodes和edges数组。
5. 每个实体只用一种类型，选择最具体的类型。
"""

USER_PROMPT_TEMPLATE = """从以下年谱条目中提取实体和关系：

日期: {date_display}
原文: {content}

请以JSON格式返回知识图谱的nodes和edges。"""
