# pragma-data-tools

**Anonymized UE5 data collection tools for Pragma AI training.**

Pragma is a fine-tuned LLM built exclusively for Unreal Engine 5 C++ developers.
These tools help contributors send real UE5 data for training — safely and privately.

---

## Tools

### `pragma_collect.py` — UE5 Source Code Collector

Scans your UE5 project, anonymizes sensitive information, and sends it via email.

```bash
py pragma_collect.py
```

**What it removes:**
- Project name → `MyProject`
- File paths → anonymized
- API keys, tokens, passwords
- Email addresses, IP addresses
- Personal file paths

**What it keeps:**
- C++ code logic
- UE5 patterns and architecture
- Error messages
- Non-sensitive comments

---

### `chat_export.py` — AI Conversation Collector

Filters UE5-related conversations from ChatGPT or Gemini exports and sends them for training.

```bash
py chat_export.py conversations.json
```

**How to export from ChatGPT:**
1. chatgpt.com → Settings → Data Controls → Export Data
2. Download the ZIP from your email
3. Extract `conversations.json`
4. Run `py chat_export.py conversations.json`

**How to export from Gemini:**
1. takeout.google.com → Select Gemini → Export
2. Download ZIP → Extract JSON file
3. Run `py chat_export.py gemini_export.json`

---

## How It Works

```
Run script
    ↓
Script scans / reads your data
    ↓
Filters UE5-related content
    ↓
Anonymizes sensitive information
    ↓
Shows you exactly what will be sent
    ↓
Asks for confirmation (y/n)
    ↓
Opens your email client (pre-filled)
    ↓
You attach ZIP and hit Send
```

No data is sent without your explicit confirmation.
Scripts are open source — you can verify exactly what they do.

---

## Requirements

```bash
pip install pathlib
```

Python 3.8+ required.

---

## Privacy

- All scripts are open source and auditable
- Nothing is sent automatically — always asks first
- No data collection without consent
- No background processes
- Email client opens locally — you control what gets sent

---

## Contributing to Pragma

Want to contribute training data?
Read the full contributor guide:

📄 `docs/Pragma_Contributor_Rehberi.docx`

Or contact us: **datacenterpragmaai@gmail.com**

---

## Related

- **Pragma AI:** Coming soon
- **forge-ue5:** [github.com/TheForgeDev/forge-ue5](https://github.com/TheForgeDev/forge-ue5)

---

## License

MIT — free to use, modify, and distribute.

---

*Built by Forge — Know Your Engine.*
