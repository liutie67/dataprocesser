import json
import os
import time
from datetime import datetime


def parse_deepseek_conversations(json_file_path, output_format="markdown"):
    """
    解析DeepSeek导出的conversations.json文件

    Args:
        json_file_path: conversations.json文件路径
        output_format: 输出格式，"markdown" 或 "txt"
    """

    # 读取JSON文件
    with open(json_file_path, 'r', encoding='utf-8') as f:
        conversations = json.load(f)

    user_path = os.path.join(os.path.dirname(json_file_path), 'user.json')
    try:
        with open(user_path, 'r', encoding='utf-8') as f:
            user = json.load(f)
            output_dir = os.path.join('converted', user.get('mobile').get('mobile_number'))
    except:
        output_dir = 'converted/default-user'
    os.makedirs(output_dir, exist_ok=True)

    for conversation in conversations:
        # 提取对话信息
        conv_id = conversation.get("id", "unknown")
        title = conversation.get("title", "无标题")
        inserted_at = conversation.get("inserted_at")

        if inserted_at:
            try:
                inserted_at = datetime.fromisoformat(inserted_at).strftime('%Y-%m-%d %H:%M:%S')
            except:
                inserted_at = str(inserted_at)

        # 构建文件名
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_title}_{conv_id[:8]}" if safe_title else f"conversation_{conv_id[:8]}"

        if output_format == "markdown":
            file_path = os.path.join(output_dir, f"{filename}.md")
            content = convert_to_markdown(conversation, title, inserted_at)
        else:
            file_path = os.path.join(output_dir, f"{filename}.txt")
            content = convert_to_txt(conversation, title, inserted_at)

        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"已导出: {file_path}")


def convert_to_markdown(conversation, title, inserted_at):
    """转换为Markdown格式"""
    content = [f"# {title}\n", f"**对话ID**: {conversation.get('id', 'unknown')}  \n",
               f"**创建时间**: {inserted_at}  \n", "\n---\n"]

    # 添加标题和信息

    # 提取并排序消息
    messages = extract_messages(conversation)

    for msg in messages:
        type = msg["type"]
        text = msg["content"]
        timestamp = msg.get("inserted_at", "")

        if timestamp:
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime('%H:%M:%S')
            except:
                timestamp = str(timestamp)

        if type == "REQUEST":
            content.append(f"\n**👤 用户** ({timestamp}):\n\n{text}\n")
        elif type == "RESPONSE":
            content.append(f"\n**🤖 助手** ({timestamp}):\n\n{text}\n")
        else:
            content.append(f"\n**⚙️ 系统** ({timestamp}):\n\n{text}\n")

    return "\n".join(content)


def convert_to_txt(conversation, title, create_time):
    """转换为TXT格式"""
    content = [f"对话标题: {title}", f"对话ID: {conversation.get('id', 'unknown')}", f"创建时间: {create_time}",
               "=" * 50]

    # 添加标题和信息

    # 提取并排序消息
    messages = extract_messages(conversation)

    for msg in messages:
        type = msg["type"]
        text = msg["content"]
        timestamp = msg.get("create_time", "")

        if timestamp:
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime('%H:%M:%S')
            except:
                timestamp = str(timestamp)

        role_map = {
            "user": "👤 用户",
            "assistant": "🤖 助手",
            "system": "⚙️ 系统"
        }

        role_display = role_map.get(type, type)
        content.append(f"\n[{role_display}] ({timestamp}):")
        content.append(text)
        content.append("-" * 30)

    return "\n".join(content)


def extract_messages(conversation):
    """从对话中提取并按时间排序消息"""
    messages = []
    mapping = conversation.get("mapping", {})

    # 找到根消息（通常没有parent的消息）
    root_messages = []
    for msg_id, msg_data in mapping.items():
        if not msg_data.get("parent"):
            root_messages.append(msg_id)

    # 递归提取所有消息
    def extract_from_node(node_id, collected_messages):
        if node_id not in mapping:
            return

        node = mapping[node_id]
        message = node.get("message")

        if message and message.get("fragments"): #and message["fragments"].get("content"):
            fragments = message.get("fragments")
            if len(fragments) > 1:
                print(f"fragments: {fragments}, 长度大于1！++++++++++++++++++++++++")
                # time.sleep(600)
            messages.append({
                "type": fragments[-1].get("type", "unknown"),
                "content": fragments[-1].get("content"),
                "inserted_at": message.get("inserted_at")
            })

        # 继续处理子消息
        for child_id in node.get("children", []):
            extract_from_node(child_id, collected_messages)

    # 从每个根节点开始提取
    for root_id in root_messages:
        extract_from_node(root_id, messages)

    # 按时间排序
    messages.sort(key=lambda x: x.get("inserted_at", 0))

    return messages


# 使用示例
if __name__ == "__main__":
    parse_deepseek_conversations("2convert/path/to/conversations.json")
