
# 🐍 Python 类型注解（Type Hint）速查表（项目参考版）

本文件用于在项目开发中统一 Python 类型注解写法，提升代码的可读性、可维护性和 IDE 辅助能力（补全、重构、跳转等）。

本文聚焦常用类型，配合简要说明和示例，便于在工程中直接参考。

---

## 📌 目录

1. 基本类型
2. 具体容器类型（list / tuple / dict / set）
3. 抽象容器类型（Sequence / Iterable / Mapping / Collection 等）
4. Optional / Union / “|” 写法与 None
5. Any：任意类型
6. 自定义类类型
7. 可变参数：*args / **kwargs
8. Callable（函数类型）
9. Literal（固定枚举值）
10. TypedDict（结构化字典类型）
11. Keyword-only 参数（* 的用法）
12. 返回值类型

---

## 1️⃣ 基本类型

最常用的基础标注：

```python
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> None:
    print(f"Hello, {name}")

def set_price(price: float, vip: bool) -> None:
    ...
```

常见基本类型：

| 类型   | 描述     |
|--------|----------|
| `int`  | 整数     |
| `float`| 浮点数   |
| `str`  | 字符串   |
| `bool` | 布尔值   |
| `None` | 空值     |

---

## 2️⃣ 具体容器类型（list / tuple / dict / set）

在 Python 3.9+ 推荐使用内置泛型语法：

```python
def sum_list(nums: list[int]) -> int:
    return sum(nums)

def point(p: tuple[int, int]) -> None:
    ...

def translate(data: dict[str, str]) -> None:
    ...

def unique_names(names: set[str]) -> set[str]:
    return set(names)
```

常见写法及含义：

| 写法               | 含义说明                                     |
|--------------------|----------------------------------------------|
| `list[int]`        | 整型列表，如 `[1, 2, 3]`                    |
| `tuple[int, int]`  | 固定两个元素的元组，例如 `(x, y)`           |
| `tuple[str, ...]`  | 任意长度、元素均为 `str` 的元组             |
| `dict[str, int]`   | 键为 `str`、值为 `int` 的字典               |
| `set[str]`         | 字符串集合，元素唯一                         |

适用场景：当明确知道要使用哪个具体容器类型时（如函数内部确实需要 list 的可变特性）可以直接用这些具体类型。

---

## 3️⃣ 抽象容器类型（Sequence / Iterable / Mapping / Collection 等）

抽象容器类型来自 `typing` 模块，代表一类“行为”而不是特定实现，更适合做函数参数类型，便于未来扩展和复用。

```python
from typing import Sequence, Iterable, Mapping, Collection
```

### 3.1 Sequence[T]

**含义：有顺序、支持 `len()` 和下标访问的只读序列视角。**

支持的典型类型：`list`、`tuple` 等。

```python
from typing import Sequence

def process_items(items: Sequence[int]) -> None:
    # items 可以是 list[int] 或 tuple[int, ...] 等
    for i in range(len(items)):
        print(i, items[i])
```

适用场景：

- 只需要“按顺序访问元素”和 `len()`，不在函数中修改容器本身。
- 希望调用方既可以传 `list`，也可以传 `tuple` 等。

### 3.2 Iterable[T]

**含义：可以用于 `for ... in` 的对象。**

```python
from typing import Iterable

def dump_all(values: Iterable[str]) -> None:
    for v in values:
        print(v)
```

支持的典型类型：`list`、`tuple`、`set`、`dict` 的 keys/values、生成器等。

适用场景：

- 只需要“遍历”，不依赖顺序、不关心是否可索引、不需要 `len()`。

### 3.3 Mapping[K, V]

**含义：键值映射类型的抽象，类似于只读视角的 `dict`。**

```python
from typing import Mapping

def print_scores(scores: Mapping[str, int]) -> None:
    for name, score in scores.items():
        print(name, score)
```

支持的典型类型：`dict[str, int]` 以及其他 dict-like 实现。

适用场景：

- 参数是“键值映射”，但不要求对方一定是内置 `dict`。
- 函数内部只读取，不改变结构。

### 3.4 Collection[T]

**含义：有长度（`len()`）、可遍历（`for`）、可做成员测试（`in`）的集合。**

```python
from typing import Collection

def has_value(values: Collection[int], target: int) -> bool:
    return target in values
```

支持的典型类型：`list`、`tuple`、`set` 等。

适用场景：

- 需要 `len()` 和 `in` 判断，但不关心顺序和具体实现。

---

### 3.5 具体容器 vs 抽象容器 的选择建议

- 如果函数 **内部需要修改列表本身**（如 `.append()`、`.sort()`），可以使用具体类型：`list[T]`
- 如果函数只要“读”，不在乎调用方传 list 还是 tuple，推荐使用抽象类型：  
  - 有顺序且需要索引：`Sequence[T]`
  - 只需要遍历：`Iterable[T]`
  - 键值映射：`Mapping[K, V]`
  - 只需 `len()` 和 `in`：`Collection[T]`

这有助于提高函数的通用性和可复用性。

---

## 4️⃣ Optional / Union / “|” 写法与 None

### 4.1 Optional[T]

`Optional[T]` 表示：**值可以是类型 `T`，也可以是 `None`**。

```python
from typing import Optional

def find_user(id: int) -> Optional[str]:
    # 找不到用户时返回 None
    ...
```

等价写法（Python 3.10+）：

```python
def find_user(id: int) -> str | None:
    ...
```

### 4.2 Union（多种可能类型）

`Union[A, B]` 表示：值可以是 `A` 或 `B` 类型。

Python 3.10 之后推荐使用“`|`”写法：

```python
def parse_num(x: int | str) -> int:
    return int(x)
```

等价的老写法：

```python
from typing import Union

def parse_num(x: Union[int, str]) -> int:
    return int(x)
```

### 4.3 Optional 与 Union 的关系

```python
from typing import Optional, Union

# 这三种写法是等价的：
Optional[str]
str | None
Union[str, None]
```

### 4.4 使用建议

- 某个参数/返回值可能为 `None`：使用 `类型 | None` 或 `Optional[类型]`
- 某个参数/返回值在几种类型中二选一或多选一：使用 `A | B | C` 或 `Union[A, B, C]`

示例：

```python
def get_config(name: str) -> dict[str, str] | None:
    # 找不到配置时返回 None
    ...

def to_str(value: int | float | str) -> str:
    return str(value)
```

---

## 5️⃣ Any（任意类型）

```python
from typing import Any

def debug(obj: Any) -> None:
    print(repr(obj))
```

`Any` 关闭了静态类型检查，相当于“我不关心这里是什么类型”。  
适合调试、日志或确实无法确定类型的情况。建议控制使用范围，避免到处传播。

---

## 6️⃣ 自定义类作为类型

自定义的类可以直接用作注解：

```python
class MonitoringAction:
    name: str
    amount: float

def run_actions(actions: list[MonitoringAction]) -> None:
    ...

def start_action(action: MonitoringAction) -> None:
    ...
```

如果只是对类做前置声明，也可以配合 `from __future__ import annotations` 避免循环引用问题。

---

## 7️⃣ 可变参数类型：*args / **kwargs

### 7.1 *args（位置参数元组）

```python
def dump(*values: int) -> None:
    # values 的类型是 tuple[int, ...]
    for v in values:
        print(v)
```

含义：可以传任意个 `int`，函数内部接收为元组。

### 7.2 **kwargs（关键字参数字典）

```python
def config(**options: str) -> None:
    # options 的类型是 dict[str, str]
    ...
```

含义：可以传任意个 `key=value`，key 为 `str`，value 为 `str`。

---

## 8️⃣ Callable：函数作为参数

```python
from typing import Callable

# 参数是一个函数，该函数接收 int，返回 str
def apply_and_print(x: int, func: Callable[[int], str]) -> None:
    result = func(x)
    print(result)

def to_hex(n: int) -> str:
    return hex(n)

apply_and_print(255, to_hex)
```

写法格式：

```text
Callable[[参数类型1, 参数类型2, ...], 返回类型]
```

---

## 9️⃣ Literal：限定固定值（类似枚举）

```python
from typing import Literal

def set_status(status: Literal["pending", "running", "done"]) -> None:
    ...
```

`status` 只能是 `"pending"`、`"running"` 或 `"done"` 三者之一，适合状态值、固定常量场景。

---

## 🔟 TypedDict：结构化字典类型

适合接口调用、配置对象等“字段固定”的字典结构。

```python
from typing import TypedDict

class RegisterPayload(TypedDict):
    account: str
    password: str
    email: str
    phone: str

def register_user(data: RegisterPayload) -> None:
    ...
```

这样 IDE 可以提示字段名，静态检查也能发现字段缺失或类型错误。

---

## 1️⃣1️⃣ Keyword-only 参数（* 的用法）

在函数定义中，`*` 用来分隔参数，使其后面的参数**只能通过关键字传入**，不能再用位置传参。

```python
from typing import Sequence

def start_monitor(
    case_id: int,
    actions: Sequence[str],
    start_time: str,
    *,
    audio_log_files: Sequence[str] | None = None,
) -> None:
    ...
```

调用示例：

```python
# 正确：audio_log_files 通过关键字传入
start_monitor(1, ["S3+5"], "2025-01-01T00:00:00", audio_log_files=["a.log", "b.log"])

# 错误：试图把 audio_log_files 当作位置参数，会触发 TypeError
# start_monitor(1, ["S3+5"], "2025-01-01T00:00:00", ["a.log"])
```

使用 keyword-only 参数的好处：

- 调用时参数含义更清晰（看到 `audio_log_files=` 就知道是干什么的）。
- 避免以后扩展参数时出现“位置顺序冲突”。

---

## 1️⃣2️⃣ 返回值类型

常见返回值标注方式：

```python
def compute() -> int:
    return 42

def do_nothing() -> None:
    pass

from typing import Iterable

def generate_numbers() -> Iterable[int]:
    yield 1
    yield 2
```

- `-> int`：返回整数
- `-> None`：无返回值（或显式返回 `None`）
- `-> Iterable[int]`：返回一个可迭代的整数序列（生成器等）

---

## ✅ 小结

在日常项目中，建议优先使用以下几类注解：

- 基本类型：`int` / `float` / `str` / `bool` / `None`
- 抽象容器：`Sequence[T]` / `Iterable[T]` / `Mapping[K, V]`
- 可空类型：`T | None`（或 `Optional[T]`）
- 自定义类 + TypedDict 表达业务结构
- 必要时使用 `Callable`、`Literal` 细化约束

合理使用类型注解可以显著提升代码质量和协作效率，推荐在新代码中尽量补充类型，旧代码可逐步演进。

