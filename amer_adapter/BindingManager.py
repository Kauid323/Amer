import sqlite3
from utils.config import sqlite_db_path
from utils import logger
import json
import logging
from .ToolManager import YunhuTools
yhtools = YunhuTools()
conn = sqlite3.connect(sqlite_db_path)
c = conn.cursor()
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor()

"""
数据表格式及数据示例

1. `QQ_table`
- 描述: 存储 QQ 群与云湖（YH）群的绑定关系。
- 字段:
  - `QQ_group_id` (TEXT, 主键): QQ 群的唯一标识符。
  - `YH_group_ids` (TEXT): 与该 QQ 群绑定的云湖群列表，存储为 JSON 格式的字符串。
  - `MC_server_ids` (TEXT): 与该 QQ 群绑定的 MC 服务器列表，存储为 JSON 格式的字符串。

- 数据示例:
{
  "QQ_group_id": "123456789",
  "YH_group_ids": [
    {
      "id": "987654321",
      "sync": true
    },
    {
      "id": "123123123",
      "sync": false
    }
  ],
  "MC_server_ids": [
    {
      "id": "10000001",
      "sync": true
    }
  ]
}

2. `YH_table`
- 描述: 存储云湖（YH）群与 QQ 群的绑定关系。
- 字段:
  - `YH_group_id` (TEXT, 主键): 云湖群的唯一标识符。
  - `QQ_group_ids` (TEXT): 与该云湖群绑定的 QQ 群列表，存储为 JSON 格式的字符串。
  - `MC_server_ids` (TEXT): 与该云湖群绑定的 MC 服务器列表，存储为 JSON 格式的字符串。

- 数据示例:
{
  "YH_group_id": "987654321",
  "QQ_group_ids": [
    {
      "id": "123456789",
      "sync": true
    },
    {
      "id": "987654321",
      "sync": false
    }
  ],
  "MC_server_ids": [
    {
      "id": "10000001",
      "sync": true
    }
  ]
}

3. `MC_table`
- 描述: 存储 Minecraft（MC）服务器与 QQ 群、云湖（YH）群的绑定关系。
- 字段:
  - `MC_server_id` (TEXT, 主键): MC 服务器的唯一标识符。
  - `QQ_group_ids` (TEXT): 与该 MC 服务器绑定的 QQ 群列表，存储为 JSON 格式的字符串。
  - `YH_group_ids` (TEXT): 与该 MC 服务器绑定的云湖群列表，存储为 JSON 格式的字符串。

- 数据示例:
{
  "MC_server_id": "10000001",
  "QQ_group_ids": [
    {
      "id": "123456789",
      "sync": true
    }
  ],
  "YH_group_ids": [
    {
      "id": "987654321",
      "sync": true
    }
  ]
}

---
数据结构说明

1. 表格设计对称性:
   - 每个表都通过主键 (`QQ_group_id`, `YH_group_id`, 或 `MC_server_id`) 唯一标识一个群组或服务器。
   - 绑定关系存储在其他字段中，使用 JSON 格式的字符串表示多个绑定对象。

2. JSON 数据结构:
   - 每个绑定对象包含以下字段：
     - `id`: 被绑定群组或服务器的唯一标识符。
     - `sync`: 表示是否同步消息的布尔值，默认为 `true`。

3. 示例解释:
   - 在 `QQ_table` 中，`QQ_group_id` 为 `"123456789"` 的群绑定了两个云湖群：`"987654321"` 和 `"123123123"`。其中，`"987654321"` 同步消息，而 `"123123123"` 不同步。此外，它还绑定了一个 MC 服务器 `"10000001"`，并同步消息。
   - 在 `YH_table` 中，`YH_group_id` 为 `"987654321"` 的群绑定了两个 QQ 群：`"123456789"` 和 `"987654321"`。其中，`"123456789"` 同步消息，而 `"987654321"` 不同步。此外，它还绑定了一个 MC 服务器 `"10000001"`，并同步消息。
   - 在 `MC_table` 中，`MC_server_id` 为 `"10000001"` 的服务器绑定了一个 QQ 群 `"123456789"` 和一个云湖群 `"987654321"`，并且两者都同步消息。

---
注意事项

1. JSON 字段的默认值:
   - 如果某个群或服务器没有绑定任何其他群或服务器，则对应的 JSON 字段应为空数组 (`[]`)。

2. 同步状态的管理:
   - `sync` 字段用于控制消息同步行为，可以通过相关接口动态更新。

3. 数据完整性:
   - 在绑定或解绑操作时，代码会同时更新 `QQ_table`、`YH_table` 和 `MC_table`，以确保数据一致性。
"""
def execute_async(async_func, *args, **kwargs):
    """
    在 ThreadPoolExecutor 中执行异步函数。
    
    :param async_func: 要执行的异步函数。
    :param args: 异步函数的位置参数。
    :param kwargs: 异步函数的关键字参数。
    """
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor,
        lambda: asyncio.run(async_func(*args, **kwargs))
    )

def get_base_sync(platform_A, platform_B, id_A, id_B):
    try:
        logger.debug(f"尝试获取 {platform_A} 和 {platform_B} 的基础同步信息")
        
        if platform_A == "QQ":
            if platform_B == "YH":
                c.execute("SELECT YH_group_ids FROM QQ_table WHERE QQ_group_id=?", (id_A,))
                row = c.fetchone()
                if row:
                    yh_group_ids = json.loads(row[0]) if row[0] else []
                    for group in yh_group_ids:
                        if group['id'] == id_B:
                            return group.get('sync', True)

        elif platform_A == "YH":
            if platform_B == "QQ":
                c.execute("SELECT QQ_group_ids FROM YH_table WHERE YH_group_id=?", (id_A,))
                row = c.fetchone()
                if row:
                    qq_group_ids = json.loads(row[0]) if row[0] else []
                    for group in qq_group_ids:
                        if group['id'] == id_B:
                            return group.get('sync', True)

        logger.debug(f"未找到 {platform_A} 和 {platform_B} 的基础同步信息")
        return None

    except sqlite3.Error as e:
        logger.error(f"获取 {platform_A} 和 {platform_B} 的基础同步信息时发生错误: {e}")
        return None

def get_info(platform, id):
    try:
        logger.debug(f"尝试获取 {platform} 的绑定信息")
        sync_other = {}
        if platform == "QQ" or platform == "qq":
            c.execute("SELECT YH_group_ids, MC_server_ids FROM QQ_table WHERE QQ_group_id=?", (id,))
            row = c.fetchone()
            if row:
                YH_group_ids = json.loads(row[0]) if row[0] else []
                MC_server_ids = json.loads(row[1]) if row[1] else []

                # 获取并设置 YH 和 MC 的 binding_sync 状态
                for group in YH_group_ids:
                    base_sync = get_base_sync("YH", "QQ", group['id'], id)
                    group['binding_sync'] = base_sync if base_sync is not None else group.get('sync', True)
                for server in MC_server_ids:
                    base_sync = get_base_sync("MC", "QQ", server['id'], id)
                    server['binding_sync'] = base_sync if base_sync is not None else server.get('sync', True)

                logger.debug(f"获取到 {platform} 的绑定信息: {YH_group_ids}, {MC_server_ids}")
                return {"status": 0, "msg": "查询成功", "data": {"YH_group_ids": YH_group_ids, "MC_server_ids": MC_server_ids}}
            else:
                return {"status": 5, "msg": "未绑定任何平台"}

        elif platform == "YH" or platform == "yh":
            c.execute("SELECT QQ_group_ids, MC_server_ids FROM YH_table WHERE YH_group_id=?", (id,))
            row = c.fetchone()
            if row:
                QQ_group_ids = json.loads(row[0]) if row[0] else []
                MC_server_ids = json.loads(row[1]) if row[1] else []

                # 获取 QQ 和 MC 的 sync 状态
                sync_other['QQ'] = {group['id']: group['sync'] for group in QQ_group_ids}
                sync_other['MC'] = {server['id']: server['sync'] for server in MC_server_ids}

                # 添加 binding_sync 到 QQ_group_ids 和 MC_server_ids
                for group in QQ_group_ids:
                    base_sync = get_base_sync("QQ", "YH", group['id'], id)
                    group['binding_sync'] = base_sync if base_sync is not None else sync_other['QQ'].get(group['id'], True)
                for server in MC_server_ids:
                    base_sync = get_base_sync("MC", "YH", server['id'], id)
                    server['binding_sync'] = base_sync if base_sync is not None else sync_other['MC'].get(server['id'], True)

                logger.debug(f"获取到 {platform} 的绑定信息: {QQ_group_ids}, {MC_server_ids}")
                return {"status": 0, "msg": "查询成功", "data": {"QQ_group_ids": QQ_group_ids, "MC_server_ids": MC_server_ids}}
            else:
                return {"status": 5, "msg": "未绑定任何平台"}

        elif platform == "MC" or platform == "mc":
            c.execute("SELECT QQ_group_ids, YH_group_ids FROM MC_table WHERE MC_server_id=?", (id,))
            row = c.fetchone()
            if row:
                QQ_group_ids = json.loads(row[0]) if row[0] else []
                YH_group_ids = json.loads(row[1]) if row[1] else []

                # 获取 QQ 和 YH 的 sync 状态
                sync_other['QQ'] = {group['id']: group['sync'] for group in QQ_group_ids}
                sync_other['YH'] = {group['id']: group['sync'] for group in YH_group_ids}

                # 添加 binding_sync 到 QQ_group_ids 和 YH_group_ids
                for group in QQ_group_ids:
                    base_sync = get_base_sync("QQ", "MC", group['id'], id)
                    group['binding_sync'] = base_sync if base_sync is not None else sync_other['QQ'].get(group['id'], True)
                for group in YH_group_ids:
                    base_sync = get_base_sync("YH", "MC", group['id'], id)
                    group['binding_sync'] = base_sync if base_sync is not None else sync_other['YH'].get(group['id'], True)

                logger.debug(f"获取到 {platform} 的绑定信息: {QQ_group_ids}, {YH_group_ids}")
                return {"status": 0, "msg": "查询成功", "data": {"QQ_group_ids": QQ_group_ids, "YH_group_ids": YH_group_ids}}
            else:
                return {"status": 5, "msg": "未绑定任何平台"}

        else:
            logger.warning(f"未知平台: {platform}")
            return {"status": 3, "msg": "未知平台"}
    except sqlite3.Error as e:
        logger.error(f"获取 {platform} 的绑定信息时发生错误: {e}")
        return None

def bind(platform_A, platform_B, id_A, id_B):
    try:
        logger.debug(f"尝试绑定 {platform_A} 和 {platform_B}")
        result = None
        if platform_A == "QQ":
            if platform_B == "YH":
                result = update_QQ_table("add", "YH", id_A, id_B)
            elif platform_B == "MC":
                result = update_QQ_table("add", "MC", id_A, id_B)
        
        elif platform_A == "YH":
            if platform_B == "QQ":
                result = update_YH_table("add", "QQ", id_A, id_B)
            elif platform_B == "MC":
                result = update_YH_table("add", "MC", id_A, id_B)

        elif platform_A == "MC":
            if platform_B == "QQ":
                result = update_MC_table("add", "QQ", id_A, id_B)
            elif platform_B == "YH":
                result = update_MC_table("add", "YH", id_A, id_B)

        else:
            logger.warning(f"未知平台: {platform_A}")
            return {"status": 3, "msg": "未知平台"}
        logger.debug(result)
        return result
    except Exception as e:
        logger.error(f"绑定失败: {e}")
        return {"status": -1, "msg": "绑定失败"}

def unbind(platform_A, platform_B, id_A, id_B):
    try:
        logger.debug(f"尝试解绑 {platform_A} 和 {platform_B}")
        if platform_A == "QQ":
            if platform_B == "YH":
                result = update_QQ_table("del", "YH", id_A, id_B)
            elif platform_B == "MC":
                result = update_QQ_table("del", "MC", id_A, id_B)

        elif platform_A == "YH":
            if platform_B == "QQ":
                result = update_YH_table("del", "QQ", id_A, id_B)
            elif platform_B == "MC":
                result = update_YH_table("del", "MC", id_A, id_B)

        elif platform_A == "MC":
            if platform_B == "QQ":
                result = update_MC_table("del", "QQ", id_A, id_B)
            elif platform_B == "YH":
                result = update_MC_table("del", "YH", id_A, id_B)

        else:
            logger.warning(f"未知平台: {platform_A}")
            return {"status": 3, "msg": "未知平台"}
        logger.debug(result)
        return result
    except Exception as e:
        logger.error(f"解绑失败: {e}")
        return {"status": -1, "msg": "解绑失败"}

def unbind_all(platform, id):
    try:
        logger.debug(f"尝试解绑所有 {platform} 和 {id}")
        if platform == "QQ" or platform == "qq":
            result = update_QQ_table("del_all", None, id, None)
        elif platform == "YH" or platform == "yh":
            result = update_YH_table("del_all", None, id, None)
        elif platform == "MC" or platform == "mc":
            result = update_MC_table("del_all", None, id, None)
        else:
            logger.warning(f"未知平台: {platform}")
            return {"status": 3, "msg": "未知平台"}
    except Exception as e:
        logger.error(f"解绑失败: {e}")
        return {"status": -1, "msg": "解绑失败"}
    finally:
        return {"status": 0, "msg": "群聊已全部解绑"}

def list_platform_table(platform, id_PF):
    try:
        if platform == "QQ" or platform == "qq":
            c.execute("SELECT * FROM QQ_table WHERE QQ_group_id=?", (id_PF,))
        elif platform == "YH" or platform == "yh":
            c.execute("SELECT * FROM YH_table WHERE YH_group_id=?", (id_PF,))
        elif platform == "MC" or platform == "mc":
            c.execute("SELECT * FROM MC_table WHERE MC_server_id=?", (id_PF,))
        else:
            logger.warning(f"未知平台: {platform}")
            return {"status": 3, "msg": "未知平台"}
        row = c.fetchone()
        return {"status": 0,"platform": platform, "data": row, "msg": "查询成功"}
    except sqlite3.Error as e:
        logger.error(f"SQLite 错误: {e}")
        return {"status": -1, "platform": platform, "data": e, "msg": "查询失败"}

def set_all_sync(platform, id_PF, sync_data):
    try:
        logger.debug(f"尝试设置 {platform} 的同步状态, ID: {id_PF}, 同步数据: {sync_data}")

        if platform == "QQ" or platform == "qq":
            result = update_QQ_table("set_all_sync", None, id_PF, None, sync_data)
        elif platform == "YH" or platform == "yh":
            result = update_YH_table("set_all_sync", None, id_PF, None, sync_data)
        elif platform == "MC" or platform == "mc":
            result = update_MC_table("set_all_sync", None, id_PF, None, sync_data)
        else:
            logger.warning(f"未知平台: {platform}")
            return {"status": 3, "msg": "未知平台"}
        
        logger.debug(result)
        return result
    except Exception as e:
        logger.error(f"设置同步状态失败: {e}")
        return {"status": -1, "msg": "设置同步状态失败"}
def set_sync(platform_A, platform_B, id_A, id_B, sync_data):
    try:
        logger.debug(f"尝试设置 {platform_A} 和 {platform_B} 的同步状态, ID: {id_A}, {id_B}, 同步数据: {sync_data}")

        if platform_A == "QQ":
            result = update_QQ_table("set_sync", platform_B, id_A, id_B, sync_data)
        elif platform_A == "YH":
            result = update_YH_table("set_sync", platform_B, id_A, id_B, sync_data)
        elif platform_A == "MC":
            result = update_MC_table("set_sync", platform_B, id_A, id_B, sync_data)
        else:
            logger.warning(f"未知平台: {platform_A}")
            return {"status": 3, "msg": "未知平台"}
        logger.debug(result)
        return result
    except Exception as e:
        logger.error(f"设置同步状态失败: {e}")
        return {"status": -1, "msg": "设置同步状态失败"}

def update_QQ_table(type, platform, id_QQ, id_PF=None, sync_data=None, called_from=None):
    try:
        logger.debug(f"尝试更新 QQ_table 类型: {type}, 平台: {platform}, ID: {id_PF}")

        # 查询现有记录
        c.execute("SELECT * FROM QQ_table WHERE QQ_group_id=?", (id_QQ,))
        existing_record = c.fetchone()
        logger.debug(f"查询结果: {existing_record}")

        if existing_record:
            yh_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
            mc_server_ids = json.loads(existing_record[2]) if existing_record[2] else []
        else:
            yh_group_ids = []
            mc_server_ids = []

        # 根据操作类型执行相应逻辑
        if type == "add":
            if platform == "YH" or platform == "yh":
                if existing_record and any(item['id'] == id_PF for item in yh_group_ids):
                    return {"status": 4, "msg": "绑定已存在"}
                yh_group_ids.append({"id": id_PF, "sync": True})
                if existing_record:
                    c.execute("UPDATE QQ_table SET YH_group_ids=? WHERE QQ_group_id=?", (json.dumps(yh_group_ids), id_QQ))
                else:
                    c.execute("INSERT INTO QQ_table (QQ_group_id, YH_group_ids) VALUES (?, ?)", (id_QQ, json.dumps(yh_group_ids)))

                # 更新 YH_table
                update_YH_table("add", "QQ", id_PF, id_QQ)
                logger.debug(f"成功添加绑定: QQ({id_QQ}) -> YH({id_PF})")

            elif platform == "MC" or platform == "mc":
                if existing_record and any(item['id'] == id_PF for item in mc_server_ids):
                    return {"status": 4, "msg": "绑定已存在"}
                mc_server_ids.append({"id": id_PF, "sync": True})
                if existing_record:
                    c.execute("UPDATE QQ_table SET MC_server_ids=? WHERE QQ_group_id=?", (json.dumps(mc_server_ids), id_QQ))
                else:
                    c.execute("INSERT INTO QQ_table (QQ_group_id, MC_server_ids) VALUES (?, ?)", (id_QQ, json.dumps(mc_server_ids)))

                # 更新 MC_table
                update_MC_table("add", "QQ", id_PF, id_QQ)
                logger.debug(f"成功添加绑定: QQ({id_QQ}) -> MC({id_PF})")

        elif type == "del":
            if platform == "YH" or platform == "yh":
                if not existing_record or not any(item['id'] == id_PF for item in yh_group_ids):
                    return {"status": 5, "msg": "绑定不存在"}
                yh_group_ids = [item for item in yh_group_ids if item['id'] != id_PF]
                c.execute("UPDATE QQ_table SET YH_group_ids=? WHERE QQ_group_id=?", (json.dumps(yh_group_ids), id_QQ))

                # 删除 YH_table 中的记录
                update_YH_table("del", "QQ", id_PF, id_QQ)
                logger.debug(f"成功删除绑定: QQ({id_QQ}) -> YH({id_PF})")

            elif platform == "MC" or platform == "mc":
                if not existing_record or not any(item['id'] == id_PF for item in mc_server_ids):
                    return {"status": 5, "msg": "绑定不存在"}
                mc_server_ids = [item for item in mc_server_ids if item['id'] != id_PF]
                c.execute("UPDATE QQ_table SET MC_server_ids=? WHERE QQ_group_id=?", (json.dumps(mc_server_ids), id_QQ))

                # 删除 MC_table 中的记录
                update_MC_table("del", "QQ", id_PF, id_QQ)
                logger.debug(f"成功删除绑定: QQ({id_QQ}) -> MC({id_PF})")

        elif type == "del_all":
            # 删除与 YH_table 的所有绑定
            if yh_group_ids:
                for item in yh_group_ids:
                    from .ToolManager import YunhuTools
                    yhtools = YunhuTools()
                    execute_async(yhtools.send, recvId=item['id'], recvType="group", contentType="text", content=f"与QQ群{id_QQ}绑定已删除")
                    logger.debug(update_YH_table("del", "QQ", item['id'], id_QQ))

            # 删除与 MC_table 的所有绑定
            if mc_server_ids:
                for item in mc_server_ids:
                    # from .ToolManager import MinecraftTools
                    # mctools = MinecraftTools()
                    # execute_async(mctools.send, recvId=item['id'], recvType="group", contentType="text", content=f"与QQ群{id_QQ}绑定已删除")
                    logger.debug(update_MC_table("del", "QQ", item['id'], id_QQ))

            # 删除 QQ_table 中的记录
            c.execute("DELETE FROM QQ_table WHERE QQ_group_id=?", (id_QQ,))
            logger.debug(f"成功删除所有绑定: QQ({id_QQ})")

        elif type == "set_sync":
            if platform == "YH" or platform == "yh":
                for item in yh_group_ids:
                    if item['id'] == id_PF:
                        item['sync'] = sync_data.get('YH', item['sync'])
                        break
                c.execute("UPDATE QQ_table SET YH_group_ids=? WHERE QQ_group_id=?", (json.dumps(yh_group_ids), id_QQ))

                # 更新 YH_table 中的同步状态
                if called_from != "YH":
                    update_YH_table("set_sync", "QQ", id_PF, id_QQ, sync_data, called_from="QQ")
                logger.debug(f"成功设置同步状态: QQ({id_QQ}) -> YH({id_PF}), sync={sync_data.get('YH')}")

            elif platform == "MC" or platform == "mc":
                for item in mc_server_ids:
                    if item['id'] == id_PF:
                        item['sync'] = sync_data.get('MC', item['sync'])
                        break
                c.execute("UPDATE QQ_table SET MC_server_ids=? WHERE QQ_group_id=?", (json.dumps(mc_server_ids), id_QQ))

                # 更新 MC_table 中的同步状态
                if called_from != "MC":
                    update_MC_table("set_sync", "QQ", id_PF, id_QQ, sync_data, called_from="QQ")
                logger.debug(f"成功设置同步状态: QQ({id_QQ}) -> MC({id_PF}), sync={sync_data.get('MC')}")

        elif type == "set_all_sync":
            for item in yh_group_ids:
                item['sync'] = sync_data.get('YH', item['sync'])
            for item in mc_server_ids:
                item['sync'] = sync_data.get('MC', item['sync'])

            # 更新 QQ_table
            c.execute("UPDATE QQ_table SET YH_group_ids=? WHERE QQ_group_id=?", (json.dumps(yh_group_ids), id_QQ))
            c.execute("UPDATE QQ_table SET MC_server_ids=? WHERE QQ_group_id=?", (json.dumps(mc_server_ids), id_QQ))

            # 更新相关表中的同步状态
            for item in yh_group_ids:
                update_YH_table("set_sync", "QQ", item['id'], id_QQ, sync_data, called_from="QQ")
            for item in mc_server_ids:
                update_MC_table("set_sync", "QQ", item['id'], id_QQ, sync_data, called_from="QQ")
            logger.debug(f"成功设置所有同步状态: QQ({id_QQ}), sync_data={sync_data}")

        conn.commit()
        return {"status": 0, "msg": "操作成功"}

    except Exception as e:
        logger.error(f"更新 QQ_table 时发生错误: {e}")
        return {"status": -1, "msg": str(e)}

def update_YH_table(type, platform, id_YH, id_PF, sync_data=None, called_from=None):
    try:
        logger.debug(f"尝试更新 YH_table 类型: {type}, 平台: {platform}, ID: {id_PF}")

        # 查询现有记录
        c.execute("SELECT * FROM YH_table WHERE YH_group_id=?", (id_YH,))
        existing_record = c.fetchone()

        if existing_record:
            if platform == "QQ" or platform == "qq":
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                logger.debug(f"查询到的 QQ_group_ids: {qq_group_ids}")
            elif platform == "MC" or platform == "mc":
                mc_server_ids = json.loads(existing_record[2]) if existing_record[2] else []
                logger.debug(f"查询到的 MC_server_ids: {mc_server_ids}")
        else:
            if platform == "QQ" or platform == "qq":
                qq_group_ids = []
            elif platform == "MC" or platform == "mc":
                mc_server_ids = []

        # 根据操作类型执行相应逻辑
        if type == "add":
            if platform == "QQ" or platform == "qq":
                if existing_record and any(item['id'] == id_PF for item in qq_group_ids):
                    return {"status": 4, "msg": "绑定已存在"}
                qq_group_ids.append({"id": id_PF, "sync": True})
                if existing_record:
                    c.execute("UPDATE YH_table SET QQ_group_ids=? WHERE YH_group_id=?", (json.dumps(qq_group_ids), id_YH))
                else:
                    c.execute("INSERT INTO YH_table (YH_group_id, QQ_group_ids) VALUES (?, ?)", (id_YH, json.dumps(qq_group_ids)))

                # 更新 QQ_table
                update_QQ_table("add", "YH", id_PF, id_YH)
                logger.debug(f"成功添加绑定: YH({id_YH}) -> QQ({id_PF})")

            elif platform == "MC" or platform == "mc":
                if existing_record and any(item['id'] == id_PF for item in mc_server_ids):
                    return {"status": 4, "msg": "绑定已存在"}
                mc_server_ids.append({"id": id_PF, "sync": True})
                if existing_record:
                    c.execute("UPDATE YH_table SET MC_server_ids=? WHERE YH_group_id=?", (json.dumps(mc_server_ids), id_YH))
                else:
                    c.execute("INSERT INTO YH_table (YH_group_id, MC_server_ids) VALUES (?, ?)", (id_YH, json.dumps(mc_server_ids)))

                # 更新 MC_table
                update_MC_table("add", "YH", id_PF, id_YH)
                logger.debug(f"成功添加绑定: YH({id_YH}) -> MC({id_PF})")

        elif type == "del":
            if platform == "QQ" or platform == "qq":
                if not existing_record or not any(item['id'] == id_PF for item in qq_group_ids):
                    return {"status": 5, "msg": "绑定不存在"}
                qq_group_ids = [item for item in qq_group_ids if item['id'] != id_PF]
                c.execute("UPDATE YH_table SET QQ_group_ids=? WHERE YH_group_id=?", (json.dumps(qq_group_ids), id_YH))

                # 删除 QQ_table 中的记录
                update_QQ_table("del", "YH", id_PF, id_YH)
                logger.debug(f"成功删除绑定: YH({id_YH}) -> QQ({id_PF})")

            elif platform == "MC" or platform == "mc":
                if not existing_record or not any(item['id'] == id_PF for item in mc_server_ids):
                    return {"status": 5, "msg": "绑定不存在"}
                mc_server_ids = [item for item in mc_server_ids if item['id'] != id_PF]
                c.execute("UPDATE YH_table SET MC_server_ids=? WHERE YH_group_id=?", (json.dumps(mc_server_ids), id_YH))

                # 删除 MC_table 中的记录
                update_MC_table("del", "YH", id_PF, id_YH)
                logger.debug(f"成功删除绑定: YH({id_YH}) -> MC({id_PF})")

        elif type == "del_all":
            # 删除与 QQ_table 的所有绑定
            c.execute("SELECT QQ_group_ids FROM YH_table WHERE YH_group_id=?", (id_YH,))
            record_to_delete = c.fetchone()
            if record_to_delete:
                qq_group_ids = json.loads(record_to_delete[0]) if record_to_delete[0] else []
                for item in qq_group_ids:
                    from .ToolManager import QQTools
                    qqtools = QQTools()
                    execute_async(qqtools.send, "group", item['id'], f"该群的云湖{id_YH}已被解绑")
                    logger.debug(f"向 QQ_group_id:{item['id']} 发送消息")
                    update_QQ_table("del", "YH", item['id'], id_YH)

            # 删除与 MC_table 的所有绑定
            c.execute("SELECT MC_server_ids FROM YH_table WHERE YH_group_id=?", (id_YH,))
            record_to_delete = c.fetchone()
            if record_to_delete:
                mc_server_ids = json.loads(record_to_delete[0]) if record_to_delete[0] else []
                for item in mc_server_ids:
                    update_MC_table("del", "YH", item['id'], id_YH)

            # 删除 YH_table 中的记录
            c.execute("DELETE FROM YH_table WHERE YH_group_id=?", (id_YH,))
            logger.debug(f"成功删除所有绑定: YH({id_YH})")

        elif type == "set_sync":
            if platform == "QQ" or platform == "qq":
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                for item in qq_group_ids:
                    if item['id'] == id_PF:
                        item['sync'] = sync_data.get('QQ', item['sync'])
                        break
                c.execute("UPDATE YH_table SET QQ_group_ids=? WHERE YH_group_id=?", (json.dumps(qq_group_ids), id_YH))

                # 更新 QQ_table 中的同步状态
                if called_from != "QQ":
                    update_QQ_table("set_sync", "YH", id_PF, id_YH, sync_data, called_from="YH")
                logger.debug(f"成功设置同步状态: YH({id_YH}) -> QQ({id_PF}), sync={sync_data.get('QQ')}")

            elif platform == "MC" or platform == "mc":
                mc_server_ids = json.loads(existing_record[2]) if existing_record[2] else []
                for item in mc_server_ids:
                    if item['id'] == id_PF:
                        item['sync'] = sync_data.get('MC', item['sync'])
                        break
                c.execute("UPDATE YH_table SET MC_server_ids=? WHERE YH_group_id=?", (json.dumps(mc_server_ids), id_YH))

                # 更新 MC_table 中的同步状态
                if called_from != "MC":
                    update_MC_table("set_sync", "YH", id_PF, id_YH, sync_data, called_from="YH")
                logger.debug(f"成功设置同步状态: YH({id_YH}) -> MC({id_PF}), sync={sync_data.get('MC')}")

        elif type == "set_all_sync":
            if existing_record:
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                mc_server_ids = json.loads(existing_record[2]) if existing_record[2] else []

                # 更新所有绑定对象的同步状态
                for item in qq_group_ids:
                    item['sync'] = sync_data.get('QQ', item['sync'])
                for item in mc_server_ids:
                    item['sync'] = sync_data.get('MC', item['sync'])

                # 更新 YH_table
                c.execute("UPDATE YH_table SET QQ_group_ids=? WHERE YH_group_id=?", (json.dumps(qq_group_ids), id_YH))
                c.execute("UPDATE YH_table SET MC_server_ids=? WHERE YH_group_id=?", (json.dumps(mc_server_ids), id_YH))

                # 更新相关表中的同步状态
                for item in qq_group_ids:
                    update_QQ_table("set_sync", "YH", item['id'], id_YH, sync_data, called_from="YH")
                for item in mc_server_ids:
                    update_MC_table("set_sync", "YH", item['id'], id_YH, sync_data, called_from="YH")
                logger.debug(f"成功设置所有同步状态: YH({id_YH}), sync_data={sync_data}")

        conn.commit()
        return {"status": 0, "msg": "操作成功"}

    except Exception as e:
        logger.error(f"更新 YH_table 时发生错误: {e}")
        return {"status": -1, "msg": str(e)}

def update_MC_table(type, platform, id_MC, id_PF, sync_data=None, called_from=None):
    try:
        logger.debug(f"尝试更新 MC_table 类型: {type}, 平台: {platform}, ID: {id_PF}")

        # 查询现有记录
        c.execute("SELECT * FROM MC_table WHERE MC_server_id=?", (id_MC,))
        existing_record = c.fetchone()

        if existing_record:
            if platform == "QQ" or platform == "qq":
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
            elif platform == "YH" or platform == "yh":
                yh_group_ids = json.loads(existing_record[2]) if existing_record[2] else []
        else:
            if platform == "QQ" or platform == "qq":
                qq_group_ids = []
            elif platform == "YH" or platform == "yh":
                yh_group_ids = []

        # 根据操作类型执行相应逻辑
        if type == "add":
            if platform == "QQ" or platform == "qq":
                if existing_record and any(item['id'] == id_PF for item in qq_group_ids):
                    return {"status": 4, "msg": "绑定已存在"}
                qq_group_ids.append({"id": id_PF, "sync": True})
                if existing_record:
                    c.execute("UPDATE MC_table SET QQ_group_ids=? WHERE MC_server_id=?", (json.dumps(qq_group_ids), id_MC))
                else:
                    c.execute("INSERT INTO MC_table (MC_server_id, QQ_group_ids) VALUES (?, ?)", (id_MC, json.dumps(qq_group_ids)))

                # 更新 QQ_table
                update_QQ_table("add", "MC", id_PF, id_MC)

            elif platform == "YH" or platform == "yh":
                if existing_record and any(item['id'] == id_PF for item in yh_group_ids):
                    return {"status": 4, "msg": "绑定已存在"}
                yh_group_ids.append({"id": id_PF, "sync": True})
                if existing_record:
                    c.execute("UPDATE MC_table SET YH_group_ids=? WHERE MC_server_id=?", (json.dumps(yh_group_ids), id_MC))
                else:
                    c.execute("INSERT INTO MC_table (MC_server_id, YH_group_ids) VALUES (?, ?)", (id_MC, json.dumps(yh_group_ids)))

                # 更新 YH_table
                update_YH_table("add", "MC", id_PF, id_MC)

        elif type == "del":
            if platform == "QQ" or platform == "qq":
                if not existing_record or not any(item['id'] == id_PF for item in qq_group_ids):
                    return {"status": 5, "msg": "绑定不存在"}
                qq_group_ids = [item for item in qq_group_ids if item['id'] != id_PF]
                c.execute("UPDATE MC_table SET QQ_group_ids=? WHERE MC_server_id=?", (json.dumps(qq_group_ids), id_MC))

                # 删除 QQ_table 中的记录
                update_QQ_table("del", "MC", id_PF, id_MC)

            elif platform == "YH" or platform == "yh":
                if not existing_record or not any(item['id'] == id_PF for item in yh_group_ids):
                    return {"status": 5, "msg": "绑定不存在"}
                yh_group_ids = [item for item in yh_group_ids if item['id'] != id_PF]
                c.execute("UPDATE MC_table SET YH_group_ids=? WHERE MC_server_id=?", (json.dumps(yh_group_ids), id_MC))

                # 删除 YH_table 中的记录
                update_YH_table("del", "MC", id_PF, id_MC)

        elif type == "del_all":
            # 删除与 QQ_table 的所有绑定
            c.execute("SELECT QQ_group_ids FROM MC_table WHERE MC_server_id=?", (id_MC,))
            record_to_delete = c.fetchone()
            if record_to_delete:
                qq_group_ids = json.loads(record_to_delete[0]) if record_to_delete[0] else []
                for item in qq_group_ids:
                    update_QQ_table("del", "MC", item['id'], id_MC)

            # 删除与 YH_table 的所有绑定
            c.execute("SELECT YH_group_ids FROM MC_table WHERE MC_server_id=?", (id_MC,))
            record_to_delete = c.fetchone()
            if record_to_delete:
                yh_group_ids = json.loads(record_to_delete[0]) if record_to_delete[0] else []
                for item in yh_group_ids:
                    update_YH_table("del", "MC", item['id'], id_MC)

            # 删除 MC_table 中的记录
            c.execute("DELETE FROM MC_table WHERE MC_server_id=?", (id_MC,))
            logger.debug(f"成功删除所有绑定: MC({id_MC})")

        elif type == "set_sync":
            if platform == "QQ" or platform == "qq":
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                for item in qq_group_ids:
                    if item['id'] == id_PF:
                        item['sync'] = sync_data.get('QQ', item['sync'])
                        break
                c.execute("UPDATE MC_table SET QQ_group_ids=? WHERE MC_server_id=?", (json.dumps(qq_group_ids), id_MC))

                # 更新 QQ_table 中的同步状态
                if called_from != "QQ":
                    update_QQ_table("set_sync", "MC", id_PF, id_MC, sync_data, called_from="MC")

            elif platform == "YH" or platform == "yh":
                yh_group_ids = json.loads(existing_record[2]) if existing_record[2] else []
                for item in yh_group_ids:
                    if item['id'] == id_PF:
                        item['sync'] = sync_data.get('YH', item['sync'])
                        break
                c.execute("UPDATE MC_table SET YH_group_ids=? WHERE MC_server_id=?", (json.dumps(yh_group_ids), id_MC))

                # 更新 YH_table 中的同步状态
                if called_from != "YH":
                    update_YH_table("set_sync", "MC", id_PF, id_MC, sync_data, called_from="MC")

        elif type == "set_all_sync":
            if existing_record:
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                yh_group_ids = json.loads(existing_record[2]) if existing_record[2] else []

                # 更新所有绑定对象的同步状态
                for item in qq_group_ids:
                    item['sync'] = sync_data.get('QQ', item['sync'])
                for item in yh_group_ids:
                    item['sync'] = sync_data.get('YH', item['sync'])

                # 更新 MC_table
                c.execute("UPDATE MC_table SET QQ_group_ids=? WHERE MC_server_id=?", (json.dumps(qq_group_ids), id_MC))
                c.execute("UPDATE MC_table SET YH_group_ids=? WHERE MC_server_id=?", (json.dumps(yh_group_ids), id_MC))

                # 更新相关表中的同步状态
                for item in qq_group_ids:
                    update_QQ_table("set_sync", "MC", item['id'], id_MC, sync_data, called_from="MC")
                for item in yh_group_ids:
                    update_YH_table("set_sync", "MC", item['id'], id_MC, sync_data, called_from="MC")

        conn.commit()
        return {"status": 0, "msg": "操作成功"}

    except Exception as e:
        logger.error(f"更新 MC_table 时发生错误: {e}")
        return {"status": -1, "msg": str(e)}