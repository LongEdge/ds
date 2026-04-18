# 04 - 节点 API 层 (nodeApi.py)

## 📋 概述

| 属性 | 值 |
|-----|-----|
| 文件 | `ai-master-svr/src/api/nodeApi.py` |
| Blueprint | `nodeBp` |
| 前缀 | `/ai-master-svr/` |
| Service | `CNodeService` |

---

## 🌐 API 路由清单

### 1. `POST /ai-master-svr/node/register/`
**功能**：注册新节点

| 参数 | 类型 | 说明 |
|-----|------|------|
| node_no | string | 节点唯一标识 |
| deal_type_no | string | 节点处理的模型类型 |
| deal_type_version | string | 模型版本 |
| node_loc | string | 节点位置/地址 |

**业务逻辑**：
```
CNodeService.create_node()
    └─ sql.add_node(node_no, deal_type_no, deal_type_version, node_loc)
```

---

### 2. `POST /ai-master-svr/node/remove/`
**功能**：注销节点

**业务逻辑**：
```
CNodeService.remove_node()
    └─ sql.remove_node(node_no)
```

---

### 3. `POST /ai-master-svr/node/update/`
**功能**：更新节点信息

---

### 4. `POST /ai-master-svr/node/bind-capability/`
**功能**：绑定节点能力（一个节点可以支持多种能力）

| 参数 | 说明 |
|-----|------|
| capability_id | 能力ID（对应模型类型） |
| node_no | 节点编号 |

**示例**：
```json
{
  "capability_id": "face_landmark",
  "node_no": "node_001"
}
```

**业务逻辑**：
```
1. 检查 capability_id 是否存在
2. 检查 node_no 是否存在
3. 绑定能力到节点
```

---

### 5. `POST /ai-master-svr/node/register-capability/`
**功能**：注册节点能力

> 类似 bind，但内部有额外校验逻辑

---

### 6. `POST /ai-master-svr/node/query-by-capability/`
**功能**：查询具有特定能力的所有节点

| 参数 | 说明 |
|-----|------|
| capability_id | 能力ID |
| page_no | 页码 |
| page_size | 每页条数 |

**返回**：
```json
{
  "code": 0,
  "msg": "查询face_landmark能力下的所有节点成功",
  "data": [...]
}
```

---

### 7. `POST /ai-master-svr/node/unbind-capability/`
**功能**：解绑节点能力

| 参数 | 说明 |
|-----|------|
| node_no | 节点编号 |
| capability_id | 能力ID |

---

### 8. `POST /ai-master-svr/node/update-capability/`
**功能**：更新节点能力状态

| 参数 | 说明 |
|-----|------|
| node_cb_id | 节点能力绑定ID |
| node_no | 节点编号 |
| node_bind_status | 绑定状态 |

---

## 🔐 权限控制现状

所有节点 API **均无认证**，任何人都可以：
- ✅ 注册虚假节点
- ✅ 注销真实节点
- ✅ 绑定/解绑任意能力

> ⚠️ 生产环境必须添加管理员权限验证

---

## 🏗️ Service 层方法

```python
class CNodeService(CBaseService):
    create_node()          # 创建节点
    remove_node()          # 删除节点
    update_node()          # 更新节点
    bind_node_capability() # 绑定能力
    register_node_capability()  # 注册能力
    query_nodes_by_capability() # 按能力查询节点
    unbind_node_capability()     # 解绑能力
    update_node_capability()    # 更新能力
```

---

## ⚠️ 潜在问题

| 问题 | 风险 |
|-----|-----|
| 节点注册无认证 | 恶意注册耗尽节点资源 |
| 无节点心跳超时 | 节点崩溃后状态不更新 |
| 能力绑定无互斥检查 | 同一能力可绑定到多个节点（取决于业务需求） |
| 无节点权重/优先级 | 任务分发无负载均衡 |
