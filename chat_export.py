
import os
import sys
import json
import re
import webbrowser
import urllib.parse
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime

PRAGMA_EMAIL = "datacenterpragmaai@gmail.com"

UE5_KEYWORDS = [
    "unreal", "ue5", "ue4", "unrealengine", "uproject",
    "uclass", "ufunction", "uproperty", "uobject",
    "aactor", "uactorcomponent", "gameplayability",
    "abilitysystemcomponent", "gameplayeffect", "gameplaytag",
    "attributeset", "gameplayability", "initabilityactorinfo",
    "hasauthority", "replication", "netmulticast",
    "server rpc", "client rpc", "breplic",
    "blueprint", "tick", "beginplay", "possess",
    "playercontroller", "playerstate", "gamemode",
    "chaos", "nanite", "lumen", "niagara",
    "lnk2019", "c2039", "uht", "hot reload",
    "output log", "crash", "callstack"
]

SENSITIVE_PATTERNS = [
    (r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]'),
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]'),
    (r'(?i)(api[_\s]?key|token|secret|password)\s*[:=]\s*\S+', '[SENSITIVE]'),
    (r'C:\\Users\\[^\\]+', 'C:\\Users\\[USER]'),
    (r'/home/[^/\s]+', '/home/[USER]'),
]

MIN_MESSAGE_LENGTH = 20
MIN_RESPONSE_LENGTH = 50

def is_ue5_related(text):
    """Metin UE5 ile ilgili mi?"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in UE5_KEYWORDS)

def anonymize(text):
    """Hassas bilgileri temizle."""
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def clean_text(text):
    """Metni temizle ve normalize et."""
    if not text:
        return ""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

def parse_chatgpt(file_path):
    """ChatGPT conversations.json dosyasını parse et."""
    conversations = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ERROR reading file: {e}")
        return []

    if isinstance(data, list):
        conv_list = data
    elif isinstance(data, dict) and "conversations" in data:
        conv_list = data["conversations"]
    else:
        print("  ERROR: Unrecognized ChatGPT export format")
        return []

    for conv in conv_list:
        try:
            messages = []
            mapping  = conv.get("mapping", {})

            for node in mapping.values():
                msg = node.get("message")
                if not msg:
                    continue

                role    = msg.get("author", {}).get("role", "")
                content = msg.get("content", {})

                if isinstance(content, dict):
                    parts = content.get("parts", [])
                    text  = " ".join(str(p) for p in parts if isinstance(p, str))
                elif isinstance(content, str):
                    text = content
                else:
                    continue

                if role in ("user", "assistant") and text.strip():
                    messages.append({"role": role, "content": text})

            if messages:
                conversations.append({
                    "title":    conv.get("title", "Untitled"),
                    "messages": messages,
                    "source":   "chatgpt"
                })
        except Exception:
            continue

    return conversations

def parse_gemini(file_path):
    """Gemini Takeout JSON dosyasını parse et."""
    conversations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ERROR reading file: {e}")
        return []

    conv_list = data if isinstance(data, list) else data.get("conversations", [])

    for conv in conv_list:
        try:
            messages = []
            for turn in conv.get("conversation", []):
                role = "user" if turn.get("type") == "human" else "assistant"
                text = turn.get("text", "")
                if text.strip():
                    messages.append({"role": role, "content": text})

            if messages:
                conversations.append({
                    "title":    conv.get("title", "Untitled"),
                    "messages": messages,
                    "source":   "gemini"
                })
        except Exception:
            continue

    return conversations

def filter_ue5_conversations(conversations):
    """UE5 ile ilgili konuşmaları filtrele."""
    filtered = []

    for conv in conversations:
        full_text = " ".join(m["content"] for m in conv["messages"])

        if not is_ue5_related(full_text):
            continue

        pairs = []
        messages = conv["messages"]

        for i in range(len(messages) - 1):
            user_msg = messages[i]
            next_msg = messages[i + 1]

            if user_msg["role"] != "user":
                continue
            if next_msg["role"] != "assistant":
                continue

            prompt     = clean_text(user_msg["content"])
            completion = clean_text(next_msg["content"])

            if len(prompt.split()) < MIN_MESSAGE_LENGTH:
                continue
            if len(completion.split()) < MIN_RESPONSE_LENGTH:
                continue

            if not is_ue5_related(prompt) and not is_ue5_related(completion):
                continue

            prompt     = anonymize(prompt)
            completion = anonymize(completion)

            pairs.append({
                "prompt":     prompt,
                "completion": completion,
                "category":   "general",
                "difficulty": "medium",
                "source":     f"chat_export_{conv['source']}"
            })

        if pairs:
            filtered.append({
                "title": conv["title"],
                "pairs": pairs
            })

    return filtered

def create_export_zip(filtered_convs, source_name):
    """Filtrelenmiş konuşmaları ZIP'e paketle."""
    tmp = tempfile.mktemp(suffix=".zip")

    total_pairs = sum(len(c["pairs"]) for c in filtered_convs)

    manifest = {
        "timestamp":   datetime.now().isoformat(),
        "source":      source_name,
        "conversations": len(filtered_convs),
        "total_pairs": total_pairs
    }

    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        lines = []
        for conv in filtered_convs:
            for pair in conv["pairs"]:
                lines.append(json.dumps(pair, ensure_ascii=False))

        zf.writestr("conversations.jsonl", "\n".join(lines))

    return tmp, total_pairs

def open_email(zip_path, total_pairs, source_name):
    """Mail istemcisini aç."""
    subject = f"[Pragma] Chat Export — {total_pairs} UE5 Q&A pairs ({source_name})"

    body = f"""Hi Pragma team,

I'd like to contribute my anonymized UE5 AI conversations for training data.

Details:
- Source: {source_name}
- UE5 Q&A pairs: {total_pairs}
- Collected with: chat_export.py

ZIP file is attached.

Generated by chat_export.py
github.com/TheForgeDev/forge-ue5
"""

    mailto = (
        f"mailto:{PRAGMA_EMAIL}"
        f"?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )

    webbrowser.open(mailto)

def detect_format(file_path):
    """Dosya formatını otomatik tespit et."""
    name = file_path.name.lower()
    if "conversation" in name or "chatgpt" in name:
        return "chatgpt"
    if "gemini" in name or "bard" in name:
        return "gemini"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            sample = f.read(500)
        if "mapping" in sample or "create_time" in sample:
            return "chatgpt"
        if "conversation" in sample:
            return "gemini"
    except Exception:
        pass

    return "unknown"

def main():
    print(f"\n{'='*60}")
    print(f"  Pragma Chat Export Collector v1.0")
    print(f"  Filters UE5 conversations for training data")
    print(f"{'='*60}\n")

    if len(sys.argv) < 2:
        print("  Usage: py chat_export.py <export_file.json>")
        print()
        print("  How to export:")
        print("  ChatGPT: Settings → Data Controls → Export Data")
        print("  Gemini:  takeout.google.com → Select Gemini")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"  ERROR: File not found: {file_path}")
        sys.exit(1)

    fmt = detect_format(file_path)
    print(f"  File:   {file_path.name}")
    print(f"  Format: {fmt}")

    print(f"\n  Parsing conversations...")
    if fmt == "chatgpt":
        conversations = parse_chatgpt(file_path)
    elif fmt == "gemini":
        conversations = parse_gemini(file_path)
    else:
        print("  ERROR: Unknown format.")
        print("  Supported: ChatGPT conversations.json, Gemini Takeout")
        sys.exit(1)

    print(f"  Total conversations found: {len(conversations)}")

    print(f"  Filtering UE5-related conversations...")
    filtered = filter_ue5_conversations(conversations)
    total_pairs = sum(len(c["pairs"]) for c in filtered)

    if not filtered:
        print("\n  No UE5-related conversations found.")
        print("  Try using UE5 C++ topics in your AI conversations first.")
        sys.exit(0)

    print(f"\n  RESULTS:")
    print(f"  UE5 conversations: {len(filtered)}")
    print(f"  Q&A pairs:         {total_pairs}")
    print()
    for conv in filtered[:5]:
        print(f"  → {conv['title'][:50]} ({len(conv['pairs'])} pairs)")
    if len(filtered) > 5:
        print(f"  ... and {len(filtered)-5} more")

    print(f"\n  PRIVACY:")
    print(f"  → Emails, IPs, API keys removed")
    print(f"  → Personal file paths anonymized")
    print(f"  → Only UE5 technical content kept")

    print()
    consent = input("  Send this data to Pragma for AI training? (y/n): ").strip().lower()

    if consent != "y":
        print("\n  Cancelled. No data was sent.")
        sys.exit(0)

    print("\n  Creating ZIP...")
    zip_path, total = create_export_zip(filtered, fmt)
    print(f"  ZIP created: {zip_path}")

    try:
        import platform
        if platform.system() == "Windows":
            import os
            os.startfile(os.path.dirname(zip_path))
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.run(["open", os.path.dirname(zip_path)])
        else:
            import subprocess
            subprocess.run(["xdg-open", os.path.dirname(zip_path)])
    except Exception:
        pass

    print("  Opening email client...")
    open_email(zip_path, total, fmt)

    print(f"\n{'='*60}")
    print(f"  Done! Please attach the ZIP and send.")
    print(f"  ZIP location: {zip_path}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
