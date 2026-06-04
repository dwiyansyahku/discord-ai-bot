"""
Utils: Helpers
Fungsi-fungsi pembantu yang dipakai di banyak tempat
"""


def split_message(text: str, max_length: int = 1900) -> list[str]:
    """Pecah pesan panjang jadi beberapa bagian agar tidak melebihi limit Discord."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Coba potong di batas kalimat/paragraf
        cut = max_length
        for sep in ['\n\n', '\n', '. ', ' ']:
            pos = text.rfind(sep, 0, max_length)
            if pos > max_length // 2:
                cut = pos + len(sep)
                break

        chunks.append(text[:cut])
        text = text[cut:]

    return chunks


def format_thinking(text: str) -> str:
    """Format respons AI dengan baik untuk Discord."""
    # Hapus multiple blank lines
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    return text.strip()


def truncate(text: str, max_len: int = 100, suffix: str = "...") -> str:
    """Potong teks dan tambah suffix jika terlalu panjang."""
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix
