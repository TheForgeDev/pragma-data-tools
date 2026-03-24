
import os
import sys
import re
import json
import zipfile
import tempfile
import webbrowser
import urllib.parse
from pathlib import Path
from datetime import datetime

PRAGMA_EMAIL     = "datacenterpragmaai@gmail.com"
MAX_FILE_SIZE_KB = 500
MAX_FILES        = 50
MAX_LINES        = 1000

COLLECT_EXTENSIONS = {".cpp", ".h", ".cs"}

SENSITIVE_PATTERNS = [
    (r'(?i)(api[_\s]?key|token|secret|password|apikey)\s*=\s*["\']?[\w\-]+["\']?', 
     'REMOVED_SENSITIVE'),
    (r'[\w\.-]+@[\w\.-]+\.\w+', 'REMOVED_EMAIL'),
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'REMOVED_IP'),
    (r'C:\\Users\\[^\\]+', 'C:\\Users\\REMOVED'),
    (r'/home/[^/]+', '/home/REMOVED'),
    (r'https?://(?!docs\.unrealengine|github\.com/EpicGames)\S+', 'REMOVED_URL'),
]

CATEGORY_KEYWORDS = {
    "gas":         ["AbilitySystemComponent", "GameplayAbility", "AttributeSet", 
                    "GameplayEffect", "GameplayTag", "UAbilitySystemInterface"],
    "multiplayer": ["HasAuthority", "IsLocallyControlled", "NetMulticast", 
                    "Server_", "Client_", "UFUNCTION.*Server", "Replicated"],
    "animation":   ["AnimInstance", "AnimMontage", "AnimNotify", "BlendSpace"],
    "blueprint":   ["BlueprintCallable", "BlueprintImplementableEvent", "UFUNCTION.*Blueprint"],
    "packaging":   ["UGameInstance", "USaveGame", "FPlatformFileManager"],
    "ui":          ["UUserWidget", "UMG", "WidgetBlueprint", "UTextBlock"],
    "threading":   ["AsyncTask", "FRunnable", "ParallelFor", "TAtomic"],
}

def find_ue5_project(start_path=None):
    """UE5 proje klasörünü bul."""
    search_paths = []
    
    if start_path:
        search_paths.append(Path(start_path))
    
    common = [
        Path.home() / "Documents" / "Unreal Projects",
        Path.home() / "UnrealProjects",
        Path("C:/UnrealProjects"),
        Path("D:/UnrealProjects"),
        Path.cwd(),
    ]
    search_paths.extend(common)
    
    for base in search_paths:
        if not base.exists():
            continue
        for uproject in base.rglob("*.uproject"):
            source_dir = uproject.parent / "Source"
            if source_dir.exists():
                return uproject.parent, source_dir
    return None, None

def detect_categories(content):
    """Kod içeriğinden UE5 kategorileri tespit et."""
    detected = set()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(kw, content):
                detected.add(cat)
                break
    return list(detected) if detected else ["general"]

def anonymize_content(content, project_name="MyProject"):
    """Hassas bilgileri temizle."""
    content = content.replace(project_name, "MyProject")
    
    for pattern, replacement in SENSITIVE_PATTERNS:
        content = re.sub(pattern, replacement, content)
    
    return content

def anonymize_path(file_path, source_dir):
    """Dosya yolunu anonymize et."""
    try:
        relative = file_path.relative_to(source_dir)
        parts = list(relative.parts)
        if parts:
            parts[0] = "MyProject"
        return str(Path(*parts))
    except ValueError:
        return file_path.name

def collect_files(source_dir, project_name):
    """Source klasöründen dosyaları topla ve temizle."""
    collected = []
    skipped   = []
    
    cpp_files = []
    for ext in COLLECT_EXTENSIONS:
        cpp_files.extend(source_dir.rglob(f"*{ext}"))
    
    cpp_files.sort(key=lambda x: x.stat().st_size)
    
    for file_path in cpp_files[:MAX_FILES]:
        try:
            size_kb = file_path.stat().st_size / 1024
            if size_kb > MAX_FILE_SIZE_KB:
                skipped.append(f"{file_path.name} (too large: {size_kb:.0f}KB)")
                continue
            
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines   = content.splitlines()
            
            if len(lines) > MAX_LINES:
                content = "\n".join(lines[:MAX_LINES])
                content += f"\n// [Truncated at {MAX_LINES} lines]"
            
            clean_content = anonymize_content(content, project_name)
            clean_path    = anonymize_path(file_path, source_dir)
            categories    = detect_categories(clean_content)
            
            collected.append({
                "path":       clean_path,
                "content":    clean_content,
                "lines":      len(lines),
                "categories": categories,
                "ext":        file_path.suffix
            })
            
        except Exception as e:
            skipped.append(f"{file_path.name} (error: {e})")
    
    return collected, skipped

def create_zip(collected, ue5_version="Unknown"):
    """Toplanan dosyaları ZIP'e paketle."""
    tmp = tempfile.mktemp(suffix=".zip")
    
    manifest = {
        "timestamp":   datetime.now().isoformat(),
        "ue5_version": ue5_version,
        "file_count":  len(collected),
        "categories":  list(set(cat for f in collected for cat in f["categories"])),
        "files":       [{"path": f["path"], "lines": f["lines"], 
                         "categories": f["categories"]} for f in collected]
    }
    
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        
        for f in collected:
            zf.writestr(f"source/{f['path']}", f["content"])
    
    return tmp, manifest

def detect_ue5_version(project_dir):
    """UE5 versiyonunu .uproject dosyasından oku."""
    for uproject in project_dir.glob("*.uproject"):
        try:
            data = json.loads(uproject.read_text())
            return data.get("EngineAssociation", "Unknown")
        except Exception:
            pass
    return "Unknown"

def open_email(zip_path, manifest):
    """Mail istemcisini aç — kullanıcı gönderir."""
    categories = ", ".join(manifest.get("categories", []))
    file_count = manifest.get("file_count", 0)
    ue5_ver    = manifest.get("ue5_version", "Unknown")
    
    subject = f"[Pragma] UE5 Code Contribution — {file_count} files"
    
    body = f"""Hi Pragma team,

I'd like to contribute my anonymized UE5 C++ code for training data.

Details:
- UE5 Version: {ue5_ver}
- Files: {file_count}
- Categories detected: {categories}
- Collected with: pragma_collect.py

ZIP file is attached.

Generated by pragma_collect.py
github.com/TheForgeDev/forge-ue5
"""
    
    mailto = (
        f"mailto:{PRAGMA_EMAIL}"
        f"?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )
    
    print(f"\n  Opening your email client...")
    print(f"  Attach this file manually: {zip_path}")
    print(f"  (It's too large to auto-attach via mailto)")
    webbrowser.open(mailto)

def main():
    print(f"\n{'='*60}")
    print(f"  Pragma Data Collector v1.0")
    print(f"  Anonymized UE5 C++ source collector")
    print(f"{'='*60}\n")
    
    print("  Searching for UE5 project...")
    project_dir, source_dir = find_ue5_project()
    
    if not source_dir:
        custom = input("  UE5 project not found. Enter path manually: ").strip()
        project_dir, source_dir = find_ue5_project(custom)
        if not source_dir:
            print("  ERROR: No UE5 project found.")
            sys.exit(1)
    
    project_name = project_dir.name
    ue5_version  = detect_ue5_version(project_dir)
    
    print(f"  Project:     {project_name} → will be anonymized as 'MyProject'")
    print(f"  UE5 Version: {ue5_version}")
    print(f"  Source dir:  {source_dir}")
    
    print(f"\n  Scanning source files...")
    collected, skipped = collect_files(source_dir, project_name)
    
    if not collected:
        print("  No files found.")
        sys.exit(1)
    
    all_cats = list(set(cat for f in collected for cat in f["categories"]))
    print(f"\n  FILES TO SEND:")
    print(f"  Count:      {len(collected)}")
    print(f"  Categories: {', '.join(all_cats)}")
    
    if skipped:
        print(f"\n  SKIPPED ({len(skipped)}):")
        for s in skipped[:5]:
            print(f"    → {s}")
    
    print(f"\n  WHAT WILL BE REMOVED:")
    print(f"  → Project name '{project_name}' → 'MyProject'")
    print(f"  → File paths anonymized")
    print(f"  → API keys, tokens, passwords")
    print(f"  → Email addresses, IP addresses")
    print(f"  → Personal file paths")
    
    print(f"\n  WHAT WILL BE KEPT:")
    print(f"  → C++ code logic")
    print(f"  → UE5 patterns and architecture")
    print(f"  → Error messages")
    print(f"  → Comments (non-sensitive)")
    
    print()
    consent = input("  Send this data to Pragma for AI training? (y/n): ").strip().lower()
    
    if consent != "y":
        print("\n  Cancelled. No data was sent.")
        sys.exit(0)
    
    print("\n  Creating anonymized ZIP...")
    zip_path, manifest = create_zip(collected, ue5_version)
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
    
    print("\n  Opening email client...")
    open_email(zip_path, manifest)
    
    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"  Please attach the ZIP file and send the email.")
    print(f"  ZIP location: {zip_path}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
