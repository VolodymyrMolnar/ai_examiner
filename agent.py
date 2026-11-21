"""Агентний цикл: Gemini (function calling) + журнал історії у форматі Message."""
import time
from datetime import datetime

from google import genai
from google.genai import errors, types

from exam_tools import ExamSession

DEFAULT_MODEL = "gemini-3.1-flash-lite"

SYSTEM_PROMPT = """Ти — AI-екзаменатор з курсу «Обробка природної мови (NLP)». \
Спілкуйся українською, доброзичливо, але професійно.

Алгоритм:
1. Привітайся та запитай у студента ім'я та email.
2. Коли маєш обоє — виклич start_exam(email, name). Якщо повернулась помилка — \
уточни дані у студента й спробуй ще раз.
3. Для кожної теми зі списку викликай get_next_topic, коли готовий до нової теми. \
Став по одному питанню за раз; на кожну тему може бути кілька ходів діалогу \
(уточнення, додаткові питання, дізнайся глибину розуміння).
4. Переходь до наступної теми, коли: (а) отримано достатньо якісну відповідь; \
(б) студент явно каже, що не знає або не може додати нічого нового; \
(в) рівень знань уже зрозумілий і подальші питання навряд чи змінять оцінку.
5. Не давай правильних відповідей під час іспиту і не підказуй прямо.
6. Після останньої теми покажи студенту оцінку (0..10) і відгук: що було добре, \
над чим попрацювати. Потім виклич end_exam(email, score). \
Історію діалогу система додасть сама.
7. Після end_exam коротко попрощайся.
Ніколи не вигадуй результат виклику інструментів."""

TOOLS = types.Tool(function_declarations=[
    {"name": "start_exam",
     "description": "Почати іспит. Перевіряє студента в базі й повертає 2-3 теми.",
     "parameters": {"type": "object", "properties": {
         "email": {"type": "string"}, "name": {"type": "string"}},
         "required": ["email", "name"]}},
    {"name": "get_next_topic",
     "description": "Отримати наступну тему для обговорення зі студентом."},
    {"name": "end_exam",
     "description": "Записати результат іспиту. Викликати після показу оцінки студенту.",
     "parameters": {"type": "object", "properties": {
         "email": {"type": "string"},
         "score": {"type": "number", "description": "Оцінка 0..10"}},
         "required": ["email", "score"]}},
])


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ExamAgent:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=90000))  # 60 с
        self.model = model
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, tools=[TOOLS],
            thinking_config=types.ThinkingConfig(thinking_level="low"))
        self.session = ExamSession()
        self.contents: list[types.Content] = []  # історія у форматі Gemini
        self.history: list[dict] = [             # формат Message з завдання
            {"role": "system", "content": SYSTEM_PROMPT, "datetime": now()}]

    def _generate(self):
        """Виклик моделі з повторами при перевантаженні (503) і логами."""
        for attempt, delay in enumerate((2, 5, 10, None), start=1):
            t = time.time()
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=self.contents, config=self.config)
                print(f"[gemini] спроба {attempt}: ок за {time.time() - t:.1f} с")
                return resp
            except errors.ServerError as e:
                print(f"[gemini] спроба {attempt}: {e.code} за {time.time() - t:.1f} с")
                if e.code != 503 or delay is None:
                    raise
                time.sleep(delay)


    def _run_tool(self, name: str, args: dict) -> dict:
        if name == "start_exam":
            return self.session.start_exam(args["email"], args["name"])
        if name == "get_next_topic":
            return self.session.get_next_topic()
        if name == "end_exam":
            # повну історію підставляє система, а не модель
            return self.session.end_exam(args["email"], args["score"], self.history)
        return {"error": f"Невідомий інструмент {name}"}

    def chat(self, user_text: str) -> str:
        """Один хід студента -> фінальна текстова відповідь бота."""
        self.contents.append(types.Content(
            role="user", parts=[types.Part(text=user_text)]))
        self.history.append({"role": "user", "content": user_text, "datetime": now()})

        for _ in range(10):  # запобіжник від нескінченного циклу інструментів
            resp = self._generate()
            if not resp.candidates or resp.candidates[0].content is None:
                return "⚠️ Модель не повернула відповідь (можливо, спрацював фільтр). Спробуйте ще раз."
            model_content = resp.candidates[0].content
            self.contents.append(model_content)

            calls = resp.function_calls or []
            if not calls:
                text = resp.text or ""
                self.history.append(
                    {"role": "system", "content": text, "datetime": now()})
                return text

            parts = []
            for call in calls:
                args = dict(call.args or {})
                out = self._run_tool(call.name, args)
                self.history.append({
                    "role": "tool_call",
                    "content": f"{call.name}({args}) -> {out}",
                    "datetime": now()})
                parts.append(types.Part.from_function_response(
                    name=call.name, response=out))
            self.contents.append(types.Content(role="user", parts=parts))
        return "⚠️ Забагато викликів інструментів підряд. Спробуйте ще раз."
