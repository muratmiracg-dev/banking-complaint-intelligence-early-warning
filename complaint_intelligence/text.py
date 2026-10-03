"""Deterministic text normalization shared by training and inference."""
import re
import hashlib


def clean_text(value):
    text = str(value or "").lower()
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b', ' ', text)
    text = re.sub(r'\b[xX]{2,}\b', ' ', text)
    text = re.sub(r'\d+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def text_hash(value):
    # Stronger normalization for cross-split duplicate detection.
    tokens = re.findall(r'\b[a-z]{2,}\b', clean_text(value))
    return hashlib.sha256(' '.join(tokens).encode()).hexdigest()


def public_excerpt(value, limit=260):
    text = re.sub(r'https?://\S+|www\.\S+', '[link]', str(value))
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '[email]', text)
    text = re.sub(r'\d[\d ()+.\-/]{5,}\d', '[number]', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit] + ('…' if len(text) > limit else '')
