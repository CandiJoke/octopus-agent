"""
Python 核心语法速览 —— 30 分钟搞定
先读一遍，然后跑一遍：python3 examples/python_basics.py
"""
import json

# ========== 1. 变量和类型（不用声明类型，Python 自己判断）==========
name = "小明"           # 字符串 str
age = 25                # 整数 int
price = 19.9            # 浮点数 float
is_active = True        # 布尔 bool
items = ["苹果", "香蕉", "橘子"]  # 列表 list（类似数组）
info = {"city": "上海", "job": "前端"}  # 字典 dict（类似对象/Map）

print(f"1. {name}今年{age}岁，在{info['city']}做{info['job']}")

# ========== 2. 条件判断（冒号开头，缩进是语法，不是装饰）==========
score = 85
if score >= 90:
    grade = "A"
elif score >= 80:       # elif = else if
    grade = "B"
else:
    grade = "C"
print(f"2. 分数{score} → {grade}")

# ========== 3. 循环 ==========
print("3. 列表循环：")
for item in items:       # 直接遍历元素，不用写 i
    print(f"   - {item}")

# ========== 4. 函数（def 定义，参数可以带默认值）==========
def greet(user_name: str, greeting: str = "你好") -> str:
    """问好函数。:str 是类型提示，不强制但推荐写。"""
    return f"{greeting}，{user_name}！"

print(f"4. {greet('小明')}")
print(f"   {greet('小明', greeting='早上好')}")

# ========== 5. 列表推导式（Python 招牌语法，一行干完循环+过滤）==========
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
evens = [n for n in numbers if n % 2 == 0]  # 取偶数
squares = [n**2 for n in numbers]            # 取平方
print(f"5. 偶数: {evens}，平方: {squares}")

# ========== 6. 字典操作（最常用的数据结构）==========
config = {"model": "gpt-4o-mini", "temperature": 0.7, "max_tokens": 1000}
print(f"6. 模型: {config['model']}")          # 取值
print(f"   温度: {config.get('temperature')}") # 安全取值（key 不存在返回 None）
print(f"   未知: {config.get('unknown', '默认值')}")  # 带默认值

for key, value in config.items():  # 遍历键值对
    print(f"   {key} = {value}")

# ========== 7. 异常处理 ==========
try:
    result = 10 / 0
except ZeroDivisionError:
    print("7. 不能除以零！")

# ========== 8. f-string（拼接字符串的神器）==========
# 注意：在 {} 里可以直接写表达式
a, b = 3, 5
print(f"8. {a} + {b} = {a + b}")

# ========== 9. 类和对象（Agent 里会用到）==========
class Tool:
    """一个工具 = 名字 + 描述 + 执行函数"""

    def __init__(self, name: str, description: str):
        """构造函数，self = Java 里的 this"""
        self.name = name
        self.description = description

    def run(self, input_data: str) -> str:
        return f"[{self.name}] 处理了: {input_data}"

search_tool = Tool("search", "搜索互联网")
print(f"9. {search_tool.run('Python教程')}")

# ========== 10. JSON 序列化（和前端交互的核心）==========
data = {
    "success": True,
    "data": {"name": "小明", "age": 25},
    "message": "操作成功"
}
json_str = json.dumps(data, ensure_ascii=False)  # Python 对象 → JSON 字符串
parsed = json.loads(json_str)                     # JSON 字符串 → Python 对象
print(f"10. JSON: {json_str}")
print(f"    解析: {parsed['data']['name']}")

print("\n✅ Python 核心语法搞定！接下来进入 Agent 实战。")
