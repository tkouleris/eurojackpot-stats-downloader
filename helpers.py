def log_to_file(message: str, log_file) -> None:
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_msg = message.strip()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {clean_msg}\n")