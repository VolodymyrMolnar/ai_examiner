"""Функції, які викликає агент: start_exam, get_next_topic, end_exam.
Замість бази даних — JSON-файли та папка results/."""
import json
import random
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
STUDENTS_FILE = BASE / "data" / "students.json"
TOPICS_FILE = BASE / "data" / "topics.json"
RESULTS_DIR = BASE / "results"


def _load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


class ExamSession:
    """Стан одного іспиту (по одному на користувача/вкладку)."""

    def __init__(self):
        self.email: str | None = None
        self.topics: list[str] = []
        self.next_index = 0
        self.finished = False

    # --- def start_exam(email, name) -> list[str] ---
    def start_exam(self, email: str, name: str) -> dict:
        students = _load(STUDENTS_FILE)
        match = next((s for s in students
                      if s["email"].lower() == email.strip().lower()), None)
        if match is None:
            return {"error": "Студента з таким email не знайдено в базі. "
                             "Уточни email у студента."}
        if match["name"].strip().lower() != name.strip().lower():
            return {"error": f"Email знайдено, але ім'я не збігається. "
                             "Уточни ім'я у студента."}
        self.email = match["email"]
        self.topics = random.sample(_load(TOPICS_FILE), k=random.choice([2, 3]))
        self.next_index = 0
        self.finished = False
        RESULTS_DIR.mkdir(exist_ok=True)
        print(f"[start_exam] {self.email} -> {self.topics}")
        return {"topics": self.topics}

    # --- def get_next_topic() -> str ---
    def get_next_topic(self) -> dict:
        if not self.topics:
            return {"error": "Іспит ще не розпочато (спочатку start_exam)."}
        if self.next_index >= len(self.topics):
            return {"topic": None, "message": "Тем більше немає. Завершуй іспит."}
        topic = self.topics[self.next_index]
        self.next_index += 1
        return {"topic": topic}

    # --- def end_exam(email, score, history) -> None ---
    def end_exam(self, email: str, score: float, history: list[dict]) -> dict:
        if self.email is None or email.strip().lower() != self.email.lower():
            return {"error": "Невідомий email або іспит не розпочато."}
        if not 0 <= score <= 10:
            return {"error": "score має бути в діапазоні 0..10."}
        RESULTS_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = RESULTS_DIR / f"{self.email}_{stamp}.json"
        out.write_text(json.dumps(
            {"email": self.email, "score": score, "topics": self.topics,
             "history": history}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        self.finished = True
        print(f"[end_exam] {self.email} score={score} -> {out.name}")
        return {"status": "saved"}
