import streamlit as st

from agent import DEFAULT_MODEL, ExamAgent

st.set_page_config(page_title="AI Examiner", page_icon="🎓")

st.title("🎓 AI Examiner — іспит з NLP")
st.markdown(
    "Чат-бот на базі Gemini, який проводить усний іспит з курсу NLP: питає ім'я та email, "
    "отримує 2–3 випадкові теми, ставить уточнювальні питання, виставляє оцінку (0–10) "
    "з відгуком і зберігає результат разом з історією діалогу.\n\n"
    "**Як користуватися:** вставте свій Gemini API-ключ (безкоштовний: aistudio.google.com/apikey) у бічній панелі "
    "(він не зберігається), напишіть «Привіт» і дотримуйтесь інструкцій бота. "
    "Тестовий студент: `test@example.com` / `Test Student`."
)

api_key = st.sidebar.text_input("Gemini API key", type="password",
                                placeholder="AIza...")
model = st.sidebar.text_input("Модель", value=DEFAULT_MODEL)
if st.sidebar.button("Почати новий іспит"):
    st.session_state.pop("agent", None)
    st.session_state.pop("chat", None)
    st.rerun()

chat = st.session_state.setdefault("chat", [])
for m in chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ваше повідомлення"):
    if not api_key:
        st.warning("Спочатку введіть API-ключ у бічній панелі.")
        st.stop()

    chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if "agent" not in st.session_state:
        st.session_state["agent"] = ExamAgent(api_key, model)

    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            try:
                reply = st.session_state["agent"].chat(prompt)
            except Exception as e:  # невірний ключ, мережа тощо
                reply = f"⚠️ Помилка: {e}"
        st.markdown(reply)
    chat.append({"role": "assistant", "content": reply})
